"""
StellarAgent SDK - AI Agent Payment SDK for Stellar Network

Enables AI agents to autonomously make micropayments via the
x402 Machine Payment Protocol on the Stellar blockchain.
"""

from src.client import StellarAgentClient
from src.models import AgentConfig, PaymentResult, EscrowBalance
from src.x402 import X402Interceptor

__version__ = "0.1.0"
__all__ = [
    "StellarAgentClient",
    "AgentConfig",
    "PaymentResult",
    "EscrowBalance",
    "X402Interceptor",
]
