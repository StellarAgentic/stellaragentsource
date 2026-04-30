"""
Unit tests for the StellarAgent SDK client and x402 interceptor.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.models import (
    AgentConfig,
    PaymentResult,
    PaymentStatus,
    X402Challenge,
    DailySpendInfo,
    EscrowBalance,
)
from src.client import StellarAgentClient, USDC_MULTIPLIER
from src.x402 import X402Interceptor


# ──────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────

def make_config(**overrides) -> AgentConfig:
    """Create a test AgentConfig with defaults."""
    defaults = dict(
        agent_id="GABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNOPQRST",
        agent_secret="SABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNOPQRST",
        daily_limit=5.0,
        per_tx_limit=1.0,
        escrow_contract_id="CCTEST123456789",
        network="testnet",
    )
    defaults.update(overrides)
    return AgentConfig(**defaults)


# ──────────────────────────────────────────────────
# Model Tests
# ──────────────────────────────────────────────────

class TestModels:
    def test_payment_result_success(self):
        result = PaymentResult(
            status=PaymentStatus.SUCCESS,
            tx_hash="abc123",
            amount=0.001,
        )
        assert result.is_success
        assert result.tx_hash == "abc123"

    def test_payment_result_failure(self):
        result = PaymentResult(
            status=PaymentStatus.FAILED,
            error="insufficient balance",
        )
        assert not result.is_success
        assert result.error == "insufficient balance"

    def test_agent_config_defaults(self):
        config = make_config()
        assert config.daily_limit == 5.0
        assert config.per_tx_limit == 1.0
        assert config.network == "testnet"
        assert config.merchant_whitelist == []

    def test_x402_challenge(self):
        challenge = X402Challenge(
            merchant_address="GMERCHANT123",
            amount=0.001,
            currency="USDC",
            resource_url="https://api.example.com/data",
        )
        assert challenge.amount == 0.001
        assert challenge.currency == "USDC"


# ──────────────────────────────────────────────────
# Client Tests
# ──────────────────────────────────────────────────

class TestStellarAgentClient:
    def test_client_initialization(self):
        config = make_config()
        client = StellarAgentClient(config)
        assert client.config.network == "testnet"
        assert client._daily_spent == 0.0
        client.close()

    def test_payment_validation_positive_amount(self):
        config = make_config()
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT", 0.5)
        assert error is None
        client.close()

    def test_payment_validation_zero_amount(self):
        config = make_config()
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT", 0)
        assert error == "Payment amount must be positive"
        client.close()

    def test_payment_validation_negative_amount(self):
        config = make_config()
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT", -1.0)
        assert error == "Payment amount must be positive"
        client.close()

    def test_payment_validation_exceeds_per_tx(self):
        config = make_config(per_tx_limit=0.5)
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT", 1.0)
        assert "exceeds per-transaction limit" in error
        client.close()

    def test_payment_validation_exceeds_daily(self):
        config = make_config(daily_limit=1.0)
        client = StellarAgentClient(config)
        client._daily_spent = 0.8
        error = client._validate_payment("GMERCHANT", 0.5)
        assert "would exceed daily limit" in error
        client.close()

    def test_payment_validation_whitelist_pass(self):
        config = make_config(merchant_whitelist=["GMERCHANT_A", "GMERCHANT_B"])
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT_A", 0.1)
        assert error is None
        client.close()

    def test_payment_validation_whitelist_fail(self):
        config = make_config(merchant_whitelist=["GMERCHANT_A"])
        client = StellarAgentClient(config)
        error = client._validate_payment("GMERCHANT_B", 0.1)
        assert "not in the whitelist" in error
        client.close()

    def test_daily_reset(self):
        config = make_config()
        client = StellarAgentClient(config)
        client._daily_spent = 4.0
        client._period_start = time.time() - 86_500  # Over a day ago
        client._maybe_reset_daily()
        assert client._daily_spent == 0.0
        client.close()

    def test_no_daily_reset_within_day(self):
        config = make_config()
        client = StellarAgentClient(config)
        client._daily_spent = 4.0
        client._period_start = time.time() - 1000  # Less than a day
        client._maybe_reset_daily()
        assert client._daily_spent == 4.0
        client.close()

    def test_pay_rejected_validation(self):
        config = make_config(per_tx_limit=0.5)
        client = StellarAgentClient(config)
        result = client.pay("GMERCHANT", 1.0)
        assert result.status == PaymentStatus.REJECTED
        assert "exceeds per-transaction limit" in result.error
        client.close()

    def test_pay_success_mock(self):
        """Test successful payment using mock (no stellar-sdk installed)."""
        config = make_config()
        client = StellarAgentClient(config)
        result = client.pay("GMERCHANT", 0.001)
        assert result.status == PaymentStatus.SUCCESS
        assert result.tx_hash != ""
        assert result.amount == 0.001
        assert client._daily_spent == 0.001
        assert client._tx_count == 1
        client.close()

    def test_pay_multiple_updates_daily_spend(self):
        config = make_config()
        client = StellarAgentClient(config)
        client.pay("GMERCHANT", 0.001)
        client.pay("GMERCHANT", 0.002)
        assert abs(client._daily_spent - 0.003) < 1e-10
        assert client._tx_count == 2
        client.close()

    def test_get_daily_spend_info(self):
        config = make_config(daily_limit=5.0)
        client = StellarAgentClient(config)
        client._daily_spent = 2.0
        info = client.get_daily_spend_info()
        assert info.amount_spent == 2.0
        assert info.daily_limit == 5.0
        assert abs(info.remaining - 3.0) < 1e-10
        client.close()

    def test_context_manager(self):
        config = make_config()
        with StellarAgentClient(config) as client:
            result = client.pay("GMERCHANT", 0.001)
            assert result.is_success


# ──────────────────────────────────────────────────
# x402 Interceptor Tests
# ──────────────────────────────────────────────────

class TestX402Interceptor:
    def test_interceptor_init(self):
        config = make_config()
        client = StellarAgentClient(config)
        interceptor = X402Interceptor(client, max_auto_pay=0.01)
        assert interceptor.max_auto_pay == 0.01
        assert interceptor.payment_history == []
        interceptor.close()
        client.close()

    def test_parse_challenge_json_body(self):
        config = make_config()
        client = StellarAgentClient(config)
        interceptor = X402Interceptor(client)

        # Mock a 402 response with JSON body
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.json.return_value = {
            "address": "GMERCHANT123",
            "amount": 0.001,
            "currency": "USDC",
        }
        mock_response.headers = {}

        challenge = interceptor._parse_challenge(mock_response, "https://api.test.com")
        assert challenge is not None
        assert challenge.merchant_address == "GMERCHANT123"
        assert challenge.amount == 0.001
        assert challenge.currency == "USDC"

        interceptor.close()
        client.close()

    def test_parse_challenge_header(self):
        config = make_config()
        client = StellarAgentClient(config)
        interceptor = X402Interceptor(client)

        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.json.side_effect = Exception("no json")
        mock_response.headers = {
            "X-PAYMENT-REQUIRED": '{"address":"GMERCHANT456","amount":0.005}',
        }

        challenge = interceptor._parse_challenge(mock_response, "https://api.test.com")
        assert challenge is not None
        assert challenge.merchant_address == "GMERCHANT456"
        assert challenge.amount == 0.005

        interceptor.close()
        client.close()

    def test_parse_challenge_www_authenticate(self):
        config = make_config()
        client = StellarAgentClient(config)
        interceptor = X402Interceptor(client)

        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.json.side_effect = Exception("no json")
        mock_response.headers = {
            "WWW-Authenticate": 'x402 address="GMERCHANT789" amount="0.002"',
        }

        challenge = interceptor._parse_challenge(mock_response, "https://api.test.com")
        assert challenge is not None
        assert challenge.merchant_address == "GMERCHANT789"
        assert challenge.amount == 0.002

        interceptor.close()
        client.close()

    def test_payment_callback(self):
        config = make_config()
        client = StellarAgentClient(config)

        payments_received = []
        interceptor = X402Interceptor(
            client,
            on_payment=lambda p: payments_received.append(p),
        )

        # Simulate a payment via pay_x402
        challenge = X402Challenge(
            merchant_address="GMERCHANT",
            amount=0.001,
        )
        result = client.pay_x402(challenge)
        assert result.is_success

        interceptor.close()
        client.close()

    def test_expired_challenge_rejected(self):
        config = make_config()
        client = StellarAgentClient(config)

        challenge = X402Challenge(
            merchant_address="GMERCHANT",
            amount=0.001,
            expires_at=time.time() - 100,  # Already expired
        )

        result = client.pay_x402(challenge)
        assert result.status == PaymentStatus.REJECTED
        assert "expired" in result.error

        client.close()


# ──────────────────────────────────────────────────
# Integration Test: End-to-End Mock Flow
# ──────────────────────────────────────────────────

class TestEndToEndMock:
    """Simulates the full e2e flow: Agent -> 402 -> Pay -> Retry -> 200"""

    def test_full_x402_flow(self):
        """
        Simulates:
        1. Agent requests data from merchant API
        2. Merchant responds with HTTP 402 + payment details
        3. SDK automatically pays via escrow
        4. SDK retries with payment proof
        5. Merchant verifies and returns data
        """
        config = make_config(daily_limit=10.0, per_tx_limit=1.0)
        client = StellarAgentClient(config)

        # Step 1-2: Parse a 402 challenge
        challenge = X402Challenge(
            merchant_address="GMERCHANT_API_PROVIDER",
            amount=0.001,
            currency="USDC",
            resource_url="https://api.merchant.com/data",
            memo="data-request-12345",
        )

        # Step 3: Execute payment
        result = client.pay_x402(challenge)

        # Step 4: Verify payment succeeded
        assert result.is_success
        assert result.tx_hash != ""
        assert result.amount == 0.001
        assert result.merchant == "GMERCHANT_API_PROVIDER"

        # Step 5: The tx_hash would be used in Authorization header
        auth_header = f"x402 {result.tx_hash}"
        assert auth_header.startswith("x402 ")
        assert len(result.tx_hash) == 64  # SHA256 hex

        # Verify local tracking
        info = client.get_daily_spend_info()
        assert info.amount_spent == 0.001
        assert info.remaining == 9.999

        client.close()

    def test_multi_payment_flow(self):
        """Test multiple sequential payments within limits."""
        config = make_config(daily_limit=1.0, per_tx_limit=0.5)
        client = StellarAgentClient(config)

        for i in range(5):
            result = client.pay("GMERCHANT", 0.1)
            assert result.is_success

        # Next payment should be fine (0.5 spent, 0.5 remaining)
        result = client.pay("GMERCHANT", 0.1)
        assert result.is_success

        # Should be at 0.6 now
        info = client.get_daily_spend_info()
        assert abs(info.amount_spent - 0.6) < 1e-10

        client.close()

    def test_daily_limit_enforcement(self):
        """Test that daily limit is enforced across multiple payments."""
        config = make_config(daily_limit=0.005, per_tx_limit=0.005)
        client = StellarAgentClient(config)

        # First few should succeed
        r1 = client.pay("GMERCHANT", 0.002)
        r2 = client.pay("GMERCHANT", 0.002)
        assert r1.is_success
        assert r2.is_success

        # This should be rejected (0.004 + 0.002 > 0.005)
        r3 = client.pay("GMERCHANT", 0.002)
        assert r3.status == PaymentStatus.REJECTED
        assert "daily limit" in r3.error

        client.close()
