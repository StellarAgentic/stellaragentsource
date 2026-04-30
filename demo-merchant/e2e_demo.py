"""
End-to-End Demo Script - StellarAgent Phase 1 Proof of Concept

Demonstrates the complete flow:
1. Developer deposits USDC into escrow (mocked)
2. AI agent is registered with spending limits
3. Agent requests data from merchant API
4. Merchant responds with HTTP 402
5. Agent SDK auto-pays via escrow
6. Agent retries with payment proof
7. Merchant verifies and serves data

Usage:
    # Start the demo merchant server first:
    python demo-merchant/server.py
    
    # Then run this demo:
    python demo-merchant/e2e_demo.py
"""

import sys
import os
import time
import json

# Add agent-sdk to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agent-sdk"))

from src.client import StellarAgentClient
from src.models import AgentConfig, X402Challenge
from src.x402 import X402Interceptor


def print_banner():
    print("=" * 64)
    print("  ⚡ StellarAgent — Phase 1 End-to-End Demo")
    print("  🌟 AI Agent Micropayment via x402 on Stellar")
    print("=" * 64)
    print()


def print_step(n: int, title: str):
    print(f"\n{'─' * 50}")
    print(f"  Step {n}: {title}")
    print(f"{'─' * 50}")


def demo_direct_payment():
    """Demo: Direct payment from agent to merchant."""
    print_banner()

    # ── Step 1: Configure the AI Agent ──
    print_step(1, "Configure AI Agent")
    config = AgentConfig(
        agent_id="GAGENT_DEMO_PUBLIC_KEY_PLACEHOLDER_1234567890ABCDEF",
        agent_secret="SAGENT_DEMO_SECRET_KEY_PLACEHOLDER_1234567890ABCDEF",
        daily_limit=5.0,
        per_tx_limit=1.0,
        escrow_contract_id="CESCROW_CONTRACT_ID_PLACEHOLDER_ON_TESTNET",
        network="testnet",
    )
    print(f"  Agent ID:      {config.agent_id[:20]}...")
    print(f"  Daily Limit:   ${config.daily_limit:.2f} USDC")
    print(f"  Per-TX Limit:  ${config.per_tx_limit:.2f} USDC")
    print(f"  Network:       {config.network}")

    # ── Step 2: Initialize the SDK Client ──
    print_step(2, "Initialize StellarAgent Client")
    client = StellarAgentClient(config)
    print("  ✅ Client initialized successfully")

    # ── Step 3: Simulate 402 Challenge ──
    print_step(3, "Simulate HTTP 402 Challenge from Merchant")
    challenge = X402Challenge(
        merchant_address="GMERCHANT_DEMO_ADDRESS_PLACEHOLDER_12345678",
        amount=0.001,
        currency="USDC",
        resource_url="https://api.merchant.com/weather/sf",
        memo="weather-data-request",
    )
    print(f"  Merchant:      {challenge.merchant_address[:20]}...")
    print(f"  Amount:        ${challenge.amount:.4f} {challenge.currency}")
    print(f"  Resource:      {challenge.resource_url}")
    print(f"  Memo:          {challenge.memo}")

    # ── Step 4: Execute Payment ──
    print_step(4, "Execute Payment via Escrow")
    result = client.pay_x402(challenge)

    if result.is_success:
        print(f"  ✅ Payment SUCCESSFUL!")
        print(f"  TX Hash:       {result.tx_hash[:32]}...")
        print(f"  Amount:        ${result.amount:.4f} USDC")
        print(f"  Merchant:      {result.merchant[:20]}...")
    else:
        print(f"  ❌ Payment FAILED: {result.error}")
        return

    # ── Step 5: Construct Auth Header ──
    print_step(5, "Construct x402 Authorization Header")
    auth_header = f"x402 {result.tx_hash}"
    print(f"  Authorization: {auth_header[:50]}...")
    print("  (Would retry the original API request with this header)")

    # ── Step 6: Check Spending Info ──
    print_step(6, "Check Agent Spending Status")
    info = client.get_daily_spend_info()
    print(f"  Daily Spent:   ${info.amount_spent:.4f} USDC")
    print(f"  Daily Limit:   ${info.daily_limit:.2f} USDC")
    print(f"  Remaining:     ${info.remaining:.4f} USDC")

    # ── Step 7: Multiple Payments ──
    print_step(7, "Execute Multiple Micropayments")
    for i in range(4):
        r = client.pay(challenge.merchant_address, 0.001)
        status = "✅" if r.is_success else "❌"
        print(f"  Payment #{i+2}: {status} | ${r.amount:.4f} USDC | TX: {r.tx_hash[:16]}...")

    info = client.get_daily_spend_info()
    print(f"\n  Total Daily Spend: ${info.amount_spent:.4f} USDC")
    print(f"  Remaining Budget:  ${info.remaining:.4f} USDC")
    print(f"  Total Transactions: {client._tx_count}")

    # ── Summary ──
    print(f"\n{'=' * 64}")
    print("  ✅ Phase 1 End-to-End Demo Complete!")
    print("  ")
    print("  Summary:")
    print(f"    • {client._tx_count} transactions executed")
    print(f"    • ${info.amount_spent:.4f} USDC total spent")
    print(f"    • All payments within spending limits")
    print(f"    • x402 payment proofs generated")
    print("=" * 64)

    client.close()


def demo_x402_interceptor():
    """Demo: Automatic x402 interception (against live merchant server)."""
    print("\n\n")
    print("=" * 64)
    print("  ⚡ x402 Interceptor Demo (requires demo merchant running)")
    print("=" * 64)

    config = AgentConfig(
        agent_id="GAGENT_DEMO_2_PUBLIC_KEY_PLACEHOLDER_123456789",
        agent_secret="SAGENT_DEMO_2_SECRET_KEY_PLACEHOLDER_123456789",
        daily_limit=10.0,
        per_tx_limit=1.0,
        escrow_contract_id="CESCROW_CONTRACT_ID_PLACEHOLDER_ON_TESTNET",
        network="testnet",
    )

    client = StellarAgentClient(config)
    interceptor = X402Interceptor(
        client,
        max_auto_pay=0.01,
        on_payment=lambda p: print(f"  💸 Payment: ${p.amount:.4f} USDC → {p.merchant[:16]}..."),
    )

    try:
        print("\n  Requesting paid resource from demo merchant...")
        response = interceptor.get("http://localhost:8402/data")
        print(f"  Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ Data received: {json.dumps(data.get('data', {}).get('message', ''), indent=2)}")
        else:
            print(f"  ⚠️  Response: {response.text[:200]}")

        print(f"\n  Payment History: {len(interceptor.payment_history)} payment(s)")
        for p in interceptor.payment_history:
            print(f"    • ${p.amount:.4f} USDC | {p.status.value} | TX: {p.tx_hash[:16]}...")
    except Exception as e:
        print(f"  ⚠️  Could not connect to merchant server: {e}")
        print("  (Start the merchant server first: python demo-merchant/server.py)")
    finally:
        interceptor.close()
        client.close()


if __name__ == "__main__":
    demo_direct_payment()

    if "--with-merchant" in sys.argv:
        demo_x402_interceptor()
