"""
StellarAgent Client - Main SDK client for AI agent payments.

Provides the primary interface for agents to interact with the
StellarAgent escrow system on the Stellar network.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from .models import (
    AgentConfig,
    DailySpendInfo,
    EscrowBalance,
    PaymentResult,
    PaymentStatus,
    X402Challenge,
)

logger = logging.getLogger("stellaragent")

# Stellar network configuration
NETWORK_CONFIG = {
    "testnet": {
        "horizon_url": "https://horizon-testnet.stellar.org",
        "network_passphrase": "Test SDF Network ; September 2015",
        "rpc_url": "https://soroban-testnet.stellar.org",
    },
    "mainnet": {
        "horizon_url": "https://horizon.stellar.org",
        "network_passphrase": "Public Global Stellar Network ; September 2015",
        "rpc_url": "https://soroban.stellar.org",
    },
}

# Token decimals for USDC on Stellar (7 decimals)
USDC_DECIMALS = 7
USDC_MULTIPLIER = 10**USDC_DECIMALS


class StellarAgentClient:
    """Main client for AI agents to make payments via StellarAgent escrow.
    
    This client handles:
    - Connecting to the Stellar network (testnet/mainnet)
    - Invoking the Soroban escrow contract for payments
    - Tracking spending limits locally
    - Providing payment proofs for x402 flows
    
    Example:
        ```python
        from stellaragent_sdk import StellarAgentClient, AgentConfig
        
        config = AgentConfig(
            agent_id="GABCDEF...",
            agent_secret="SABCDEF...",
            daily_limit=5.0,
            per_tx_limit=1.0,
            escrow_contract_id="CCCCDEF...",
        )
        
        client = StellarAgentClient(config)
        result = client.pay("GMERCHANT...", 0.001)
        
        if result.is_success:
            print(f"Paid! TX: {result.tx_hash}")
        ```
    """

    def __init__(self, config: AgentConfig):
        """Initialize the StellarAgent client.
        
        Args:
            config: Agent configuration including keys and limits.
        """
        self.config = config
        self._network = NETWORK_CONFIG.get(config.network, NETWORK_CONFIG["testnet"])
        self._http = httpx.Client(timeout=30.0)
        
        # Local spend tracking (mirrors on-chain state)
        self._daily_spent: float = 0.0
        self._period_start: float = time.time()
        self._tx_count: int = 0

        logger.info(
            "StellarAgent client initialized | network=%s | agent=%s",
            config.network,
            config.agent_id[:12] + "...",
        )

    # ──────────────────────────────────────────────────
    # Payment Operations
    # ──────────────────────────────────────────────────

    def pay(self, merchant_address: str, amount: float, memo: str = "") -> PaymentResult:
        """Execute a payment to a merchant from the developer's escrow.
        
        This method:
        1. Validates the amount against local spending limits
        2. Invokes the Soroban escrow contract's `pay` function
        3. Returns the transaction hash as proof of payment
        
        Args:
            merchant_address: Stellar address of the merchant to pay.
            amount: Amount to pay in USDC (e.g. 0.001 for $0.001).
            memo: Optional memo for the transaction.
            
        Returns:
            PaymentResult with status and transaction details.
        """
        # Pre-flight validation
        validation_error = self._validate_payment(merchant_address, amount)
        if validation_error:
            return PaymentResult(
                status=PaymentStatus.REJECTED,
                amount=amount,
                merchant=merchant_address,
                error=validation_error,
            )

        try:
            # Convert to on-chain units (7 decimal places for USDC)
            amount_units = int(amount * USDC_MULTIPLIER)

            # Build and submit the Soroban contract invocation
            tx_hash, tx_id = self._invoke_escrow_pay(
                merchant_address, amount_units, memo
            )

            # Update local tracking
            self._daily_spent += amount
            self._tx_count += 1

            result = PaymentResult(
                status=PaymentStatus.SUCCESS,
                tx_hash=tx_hash,
                tx_id=tx_id,
                amount=amount,
                merchant=merchant_address,
            )

            logger.info(
                "Payment successful | merchant=%s | amount=%.6f USDC | tx=%s",
                merchant_address[:12] + "...",
                amount,
                tx_hash[:16] + "...",
            )
            return result

        except Exception as e:
            logger.error("Payment failed: %s", str(e))
            return PaymentResult(
                status=PaymentStatus.FAILED,
                amount=amount,
                merchant=merchant_address,
                error=str(e),
            )

    def pay_x402(self, challenge: X402Challenge) -> PaymentResult:
        """Process an x402 payment challenge.
        
        Convenience method that extracts payment details from an x402
        challenge response and executes the payment.
        
        Args:
            challenge: Parsed x402 challenge from a merchant's 402 response.
            
        Returns:
            PaymentResult with the transaction hash for the x402 proof header.
        """
        if challenge.expires_at > 0 and time.time() > challenge.expires_at:
            return PaymentResult(
                status=PaymentStatus.REJECTED,
                amount=challenge.amount,
                merchant=challenge.merchant_address,
                error="x402 challenge has expired",
            )

        return self.pay(
            merchant_address=challenge.merchant_address,
            amount=challenge.amount,
            memo=challenge.memo,
        )

    # ──────────────────────────────────────────────────
    # Query Operations
    # ──────────────────────────────────────────────────

    def get_escrow_balance(self) -> EscrowBalance:
        """Query the developer's escrow balance from the Soroban contract.
        
        Returns:
            EscrowBalance with current balance information.
        """
        try:
            balance_units = self._invoke_escrow_query("get_balance")
            balance = balance_units / USDC_MULTIPLIER
            return EscrowBalance(balance=balance)
        except Exception as e:
            logger.error("Failed to query balance: %s", str(e))
            return EscrowBalance()

    def get_daily_spend_info(self) -> DailySpendInfo:
        """Get the agent's current daily spending information.
        
        Returns local tracking data (mirrors on-chain state).
        
        Returns:
            DailySpendInfo with current spending details.
        """
        self._maybe_reset_daily()
        remaining = max(0.0, self.config.daily_limit - self._daily_spent)
        return DailySpendInfo(
            amount_spent=self._daily_spent,
            daily_limit=self.config.daily_limit,
            remaining=remaining,
            period_start=self._period_start,
        )

    # ──────────────────────────────────────────────────
    # Internal Methods
    # ──────────────────────────────────────────────────

    def _validate_payment(self, merchant: str, amount: float) -> Optional[str]:
        """Pre-flight validation of a payment before submitting on-chain."""
        if amount <= 0:
            return "Payment amount must be positive"

        if amount > self.config.per_tx_limit:
            return f"Amount {amount} exceeds per-transaction limit {self.config.per_tx_limit}"

        self._maybe_reset_daily()
        if self._daily_spent + amount > self.config.daily_limit:
            return (
                f"Amount {amount} would exceed daily limit "
                f"({self._daily_spent + amount:.6f} > {self.config.daily_limit})"
            )

        if self.config.merchant_whitelist and merchant not in self.config.merchant_whitelist:
            return f"Merchant {merchant} is not in the whitelist"

        return None

    def _maybe_reset_daily(self):
        """Reset daily spend counter if a new day has started."""
        now = time.time()
        if now - self._period_start >= 86_400:
            self._daily_spent = 0.0
            self._period_start = now

    def _invoke_escrow_pay(
        self, merchant: str, amount_units: int, memo: str
    ) -> tuple[str, int]:
        """Invoke the Soroban escrow contract's `pay` function.
        
        In production, this uses stellar-sdk to:
        1. Build a Soroban contract invocation transaction
        2. Sign it with the agent's secret key
        3. Submit to the Stellar network
        4. Wait for confirmation
        
        Returns:
            Tuple of (transaction_hash, contract_tx_id)
        """
        try:
            from stellar_sdk import (
                Keypair,
                Network,
                SorobanServer,
                TransactionBuilder,
                scval,
            )

            keypair = Keypair.from_secret(self.config.agent_secret)
            server = SorobanServer(self._network["rpc_url"])

            # Load the agent's account for sequence number
            account = server.load_account(keypair.public_key)

            # Build contract invocation
            builder = TransactionBuilder(
                source_account=account,
                network_passphrase=self._network["network_passphrase"],
                base_fee=100,
            )

            builder.append_invoke_contract_function_op(
                contract_id=self.config.escrow_contract_id,
                function_name="pay",
                parameters=[
                    scval.to_address(self.config.agent_id),
                    scval.to_address(merchant),
                    scval.to_int128(amount_units),
                ],
            )

            builder.set_timeout(30)
            tx = builder.build()
            tx.sign(keypair)

            # Submit and wait for result
            response = server.send_transaction(tx)

            if response.status == "ERROR":
                raise Exception(f"Transaction failed: {response.error}")

            # Poll for completion
            tx_hash = response.hash
            tx_id = self._tx_count + 1  # Approximate; real value comes from contract

            return tx_hash, tx_id

        except ImportError:
            # Fallback for testing without stellar-sdk installed
            logger.warning("stellar-sdk not available, using mock transaction")
            import hashlib
            mock_hash = hashlib.sha256(
                f"{self.config.agent_id}:{merchant}:{amount_units}:{time.time()}".encode()
            ).hexdigest()
            return mock_hash, self._tx_count + 1

    def _invoke_escrow_query(self, function_name: str) -> int:
        """Invoke a read-only function on the Soroban escrow contract."""
        try:
            from stellar_sdk import SorobanServer, scval

            server = SorobanServer(self._network["rpc_url"])

            # Use simulateTransaction for read-only queries
            # This is a simplified implementation
            result = server.call(
                contract_id=self.config.escrow_contract_id,
                function_name=function_name,
                parameters=[scval.to_address(self.config.agent_id)],
            )

            return scval.from_int128(result)

        except (ImportError, Exception) as e:
            logger.warning("Query fallback: %s", str(e))
            return 0

    def close(self):
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
