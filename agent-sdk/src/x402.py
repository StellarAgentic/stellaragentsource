"""
x402 Machine Payment Protocol Interceptor for StellarAgent.

Automatically detects HTTP 402 Payment Required responses,
parses the payment challenge, and executes payment via the
Stellar escrow system.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional, Callable

import httpx

from .client import StellarAgentClient
from .models import PaymentResult, PaymentStatus, X402Challenge

logger = logging.getLogger("stellaragent.x402")

# Header names used in the x402 protocol
X402_PAYMENT_HEADER = "X-PAYMENT"
X402_PAYMENT_REQUIRED_HEADER = "X-PAYMENT-REQUIRED"


class X402Interceptor:
    """HTTP interceptor that automatically handles x402 payment challenges.
    
    Wraps an HTTP client to detect 402 responses, extract payment details,
    execute payment via the StellarAgent escrow, and retry the original
    request with payment proof.
    
    Example:
        ```python
        from stellaragent_sdk import StellarAgentClient, X402Interceptor, AgentConfig
        
        config = AgentConfig(
            agent_id="GABCDEF...",
            agent_secret="SABCDEF...",
            escrow_contract_id="CCCCDEF...",
        )
        
        client = StellarAgentClient(config)
        interceptor = X402Interceptor(client)
        
        # This will automatically handle 402 challenges
        response = interceptor.get("https://api.merchant.com/data")
        print(response.text)
        ```
    """

    def __init__(
        self,
        agent_client: StellarAgentClient,
        max_auto_pay: float = 0.01,
        on_payment: Optional[Callable[[PaymentResult], None]] = None,
    ):
        """Initialize the x402 interceptor.
        
        Args:
            agent_client: StellarAgent client for making payments.
            max_auto_pay: Maximum amount to auto-pay without confirmation (USDC).
            on_payment: Optional callback invoked after each payment attempt.
        """
        self.agent = agent_client
        self.max_auto_pay = max_auto_pay
        self.on_payment = on_payment
        self._http = httpx.Client(timeout=30.0)
        self._payment_history: list[PaymentResult] = []

    # ──────────────────────────────────────────────────
    # HTTP Methods with x402 handling
    # ──────────────────────────────────────────────────

    def get(self, url: str, **kwargs) -> httpx.Response:
        """HTTP GET with automatic x402 payment handling."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        """HTTP POST with automatic x402 payment handling."""
        return self._request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        """HTTP PUT with automatic x402 payment handling."""
        return self._request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        """HTTP DELETE with automatic x402 payment handling."""
        return self._request("DELETE", url, **kwargs)

    # ──────────────────────────────────────────────────
    # Core Logic
    # ──────────────────────────────────────────────────

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with x402 interception.
        
        Flow:
        1. Make the initial request
        2. If 402 received, parse the payment challenge
        3. Execute payment via StellarAgent escrow
        4. Retry request with payment proof header
        """
        response = self._http.request(method, url, **kwargs)

        if response.status_code != 402:
            return response

        logger.info("Received HTTP 402 from %s — initiating x402 payment", url)

        # Parse the 402 challenge
        challenge = self._parse_challenge(response, url)
        if not challenge:
            logger.error("Could not parse x402 challenge from %s", url)
            return response

        # Check auto-pay threshold
        if challenge.amount > self.max_auto_pay:
            logger.warning(
                "x402 amount %.6f exceeds auto-pay limit %.6f — skipping",
                challenge.amount,
                self.max_auto_pay,
            )
            return response

        # Execute payment
        payment_result = self.agent.pay_x402(challenge)
        self._payment_history.append(payment_result)

        if self.on_payment:
            self.on_payment(payment_result)

        if not payment_result.is_success:
            logger.error(
                "x402 payment failed: %s",
                payment_result.error,
            )
            return response

        # Retry with payment proof
        logger.info("x402 payment successful, retrying request with proof")
        headers = kwargs.pop("headers", {}) or {}
        headers[X402_PAYMENT_HEADER] = payment_result.tx_hash
        headers["Authorization"] = f"x402 {payment_result.tx_hash}"

        return self._http.request(method, url, headers=headers, **kwargs)

    def _parse_challenge(
        self, response: httpx.Response, url: str
    ) -> Optional[X402Challenge]:
        """Parse an x402 payment challenge from a 402 response.
        
        Supports multiple challenge formats:
        1. JSON body with payment details
        2. X-PAYMENT-REQUIRED header
        3. WWW-Authenticate header
        """
        # Try JSON body first
        try:
            body = response.json()
            if isinstance(body, dict):
                return X402Challenge(
                    merchant_address=body.get("address", body.get("stellar_address", "")),
                    amount=float(body.get("amount", 0)),
                    currency=body.get("currency", "USDC"),
                    resource_url=url,
                    expires_at=float(body.get("expires_at", 0)),
                    memo=body.get("memo", ""),
                )
        except Exception:
            pass

        # Try X-PAYMENT-REQUIRED header
        payment_header = response.headers.get(X402_PAYMENT_REQUIRED_HEADER, "")
        if payment_header:
            try:
                data = json.loads(payment_header)
                return X402Challenge(
                    merchant_address=data.get("address", ""),
                    amount=float(data.get("amount", 0)),
                    currency=data.get("currency", "USDC"),
                    resource_url=url,
                )
            except (json.JSONDecodeError, ValueError):
                pass

        # Try WWW-Authenticate header (x402 format)
        www_auth = response.headers.get("WWW-Authenticate", "")
        if "x402" in www_auth.lower():
            match = re.search(
                r'address="([^"]+)".*amount="([^"]+)"',
                www_auth,
            )
            if match:
                return X402Challenge(
                    merchant_address=match.group(1),
                    amount=float(match.group(2)),
                    resource_url=url,
                )

        return None

    @property
    def payment_history(self) -> list[PaymentResult]:
        """Get the history of all payment attempts made by this interceptor."""
        return list(self._payment_history)

    def close(self):
        """Close the HTTP client."""
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
