"""
Data models for the StellarAgent SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import time


class PaymentStatus(str, Enum):
    """Status of a payment transaction."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"  # Rejected by spending limits


@dataclass
class AgentConfig:
    """Configuration for an AI agent's spending capabilities.
    
    Attributes:
        agent_id: Unique identifier / Stellar public key for the agent.
        agent_secret: Secret key for signing transactions.
        daily_limit: Maximum daily spend in USDC (human-readable, e.g. 5.0 = $5).
        per_tx_limit: Maximum per-transaction spend in USDC.
        escrow_contract_id: Soroban contract ID for the escrow.
        network: Stellar network to use ('testnet' or 'mainnet').
        merchant_whitelist: Optional list of allowed merchant addresses.
    """
    agent_id: str
    agent_secret: str
    daily_limit: float = 5.0
    per_tx_limit: float = 1.0
    escrow_contract_id: str = ""
    network: str = "testnet"
    merchant_whitelist: list[str] = field(default_factory=list)


@dataclass
class PaymentResult:
    """Result of a payment transaction.
    
    Attributes:
        status: Payment status.
        tx_hash: Stellar transaction hash (if successful).
        tx_id: Contract-level transaction ID.
        amount: Amount paid in USDC.
        merchant: Merchant address that received payment.
        timestamp: Unix timestamp of the payment.
        error: Error message if payment failed.
    """
    status: PaymentStatus
    tx_hash: str = ""
    tx_id: int = 0
    amount: float = 0.0
    merchant: str = ""
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.status == PaymentStatus.SUCCESS


@dataclass
class EscrowBalance:
    """Developer's escrow balance information.
    
    Attributes:
        developer: Developer's Stellar address.
        balance: Current balance in USDC.
        total_deposited: Total amount ever deposited.
        total_spent: Total amount spent by agents.
    """
    developer: str = ""
    balance: float = 0.0
    total_deposited: float = 0.0
    total_spent: float = 0.0


@dataclass 
class X402Challenge:
    """Parsed x402 Payment Required challenge from a merchant.
    
    Attributes:
        merchant_address: Stellar address to pay.
        amount: Amount required in USDC.
        currency: Currency code (e.g. 'USDC').
        resource_url: The URL that requires payment.
        expires_at: Timestamp when the challenge expires.
        memo: Optional memo for the transaction.
    """
    merchant_address: str
    amount: float
    currency: str = "USDC"
    resource_url: str = ""
    expires_at: float = 0.0
    memo: str = ""


@dataclass
class DailySpendInfo:
    """Agent's daily spending information.
    
    Attributes:
        amount_spent: Total spent in current period.
        daily_limit: Maximum allowed daily spend.
        remaining: How much the agent can still spend today.
        period_start: Start of the current spending period.
    """
    amount_spent: float = 0.0
    daily_limit: float = 0.0
    remaining: float = 0.0
    period_start: float = 0.0
