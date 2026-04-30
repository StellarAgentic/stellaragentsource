"""
Demo Merchant Server - Simulates a paywalled API that enforces HTTP 402.

This server demonstrates the x402 payment flow:
1. Client requests a resource
2. Server responds with 402 + payment details
3. Client pays and retries with proof
4. Server verifies and returns data
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import hashlib
import time
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo-merchant")

# Configuration
MERCHANT_ADDRESS = "GDEMO_MERCHANT_STELLAR_ADDRESS_PLACEHOLDER"
PRICE_PER_REQUEST = 0.001  # 0.001 USDC per API call
PORT = 8402

# In-memory store of verified payment hashes
verified_payments: set[str] = set()


class MerchantHandler(BaseHTTPRequestHandler):
    """HTTP handler implementing x402 payment flow."""

    def do_GET(self):
        if self.path == "/health":
            self._respond_json(200, {"status": "ok", "merchant": "StellarAgent Demo"})
            return

        if self.path == "/data" or self.path.startswith("/api/"):
            self._handle_paid_resource()
            return

        if self.path == "/payments":
            self._respond_json(200, {
                "verified_count": len(verified_payments),
                "payments": list(verified_payments)[-10:],
            })
            return

        self._respond_json(404, {"error": "not found"})

    def _handle_paid_resource(self):
        """Handle a request for a paid resource with x402 enforcement."""

        # Check for payment proof
        auth_header = self.headers.get("Authorization", "")
        x_payment = self.headers.get("X-PAYMENT", "")

        tx_hash = ""

        if auth_header.startswith("x402 "):
            tx_hash = auth_header[5:].strip()
        elif x_payment:
            tx_hash = x_payment.strip()

        if tx_hash:
            # Verify the payment hash
            if self._verify_payment(tx_hash):
                logger.info("✅ Payment verified: %s", tx_hash[:16] + "...")
                self._serve_data(tx_hash)
                return
            else:
                logger.warning("❌ Invalid payment hash: %s", tx_hash[:16] + "...")
                self._respond_json(403, {"error": "invalid payment proof"})
                return

        # No payment — respond with 402 challenge
        logger.info("💰 Sending 402 challenge to client")
        self._send_402_challenge()

    def _send_402_challenge(self):
        """Send an HTTP 402 Payment Required response with x402 details."""
        challenge = {
            "status": 402,
            "message": "Payment required to access this resource",
            "address": MERCHANT_ADDRESS,
            "amount": PRICE_PER_REQUEST,
            "currency": "USDC",
            "network": "stellar:testnet",
            "expires_at": time.time() + 300,  # 5 minute expiry
            "memo": f"api-access-{int(time.time())}",
        }

        self.send_response(402)
        self.send_header("Content-Type", "application/json")
        self.send_header(
            "X-PAYMENT-REQUIRED",
            json.dumps({
                "address": MERCHANT_ADDRESS,
                "amount": PRICE_PER_REQUEST,
                "currency": "USDC",
            }),
        )
        self.send_header(
            "WWW-Authenticate",
            f'x402 address="{MERCHANT_ADDRESS}" amount="{PRICE_PER_REQUEST}" '
            f'currency="USDC" network="stellar:testnet"',
        )
        self.end_headers()
        self.wfile.write(json.dumps(challenge).encode())

    def _verify_payment(self, tx_hash: str) -> bool:
        """Verify a payment hash.
        
        In production, this would:
        1. Query Stellar RPC to confirm the transaction exists
        2. Verify the correct amount was sent to the merchant address
        3. Check the transaction hasn't been used before (replay protection)
        
        For the demo, we accept any valid-looking hash.
        """
        if len(tx_hash) < 16:
            return False

        if tx_hash in verified_payments:
            logger.warning("Replay attempt detected: %s", tx_hash[:16])
            return False  # Replay protection

        # In demo mode, accept any plausible hash
        verified_payments.add(tx_hash)
        return True

    def _serve_data(self, tx_hash: str):
        """Serve the actual API data after successful payment."""
        data = {
            "status": "success",
            "data": {
                "message": "🎉 Access granted via x402 micropayment!",
                "timestamp": time.time(),
                "weather": {
                    "location": "San Francisco, CA",
                    "temperature": 68,
                    "unit": "F",
                    "conditions": "Partly Cloudy",
                    "humidity": 62,
                },
                "payment_info": {
                    "tx_hash": tx_hash,
                    "amount_paid": PRICE_PER_REQUEST,
                    "currency": "USDC",
                    "merchant": MERCHANT_ADDRESS,
                },
            },
        }
        self._respond_json(200, data)

    def _respond_json(self, status: int, data: dict):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def log_message(self, format, *args):
        """Override to use our logger."""
        logger.info(format, *args)


def main():
    server = HTTPServer(("0.0.0.0", PORT), MerchantHandler)
    logger.info("=" * 60)
    logger.info("🏪 StellarAgent Demo Merchant Server")
    logger.info("   Listening on http://localhost:%d", PORT)
    logger.info("   Merchant Address: %s", MERCHANT_ADDRESS)
    logger.info("   Price per request: %.4f USDC", PRICE_PER_REQUEST)
    logger.info("=" * 60)
    logger.info("")
    logger.info("Endpoints:")
    logger.info("   GET /data      - Paid resource (triggers x402)")
    logger.info("   GET /health    - Health check (free)")
    logger.info("   GET /payments  - View recent payments (free)")
    logger.info("")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down merchant server")
        server.server_close()


if __name__ == "__main__":
    main()
