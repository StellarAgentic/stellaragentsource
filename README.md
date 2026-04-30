# StellarAgent ⚡

> AI Agent Escrow & Identity Portal on the Stellar Network

StellarAgent bridges the gap between autonomous AI agents and web infrastructure by providing seamless, frictionless on-chain micropayments and identity verification via Stellar's Soroban smart contracts and the x402 Machine Payment Protocol.

## 🏗️ Project Structure

```
stellaragentsource/
├── contracts/
│   └── stellar-agent-escrow/    # Soroban smart contract (Rust)
│       └── src/
│           ├── lib.rs            # Contract entry point
│           ├── escrow.rs         # Core escrow logic
│           ├── types.rs          # Data types & storage keys
│           └── test.rs           # Comprehensive unit tests
├── agent-sdk/                    # Python Agent SDK
│   ├── src/
│   │   ├── client.py            # Main SDK client
│   │   ├── models.py            # Data models
│   │   └── x402.py              # x402 protocol interceptor
│   └── tests/
│       └── test_sdk.py          # SDK unit tests
├── dashboard/                    # React Developer Dashboard (Vite)
│   └── src/
│       ├── App.jsx              # Dashboard application
│       └── index.css            # Design system
├── demo-merchant/                # Demo merchant server
│   ├── server.py                # HTTP 402 merchant mock
│   └── e2e_demo.py             # End-to-end demo script
├── Architecture.md              # System architecture
├── PRD.md                       # Product requirements
└── Roadmap.md                   # Project roadmap
```

## 🚀 Quick Start

### 1. Smart Contract (Soroban)

```bash
# Prerequisites: Rust + Stellar CLI
rustup target add wasm32v1-none
cargo install --locked stellar-cli@25.1.0

# Build the contract
cd contracts/stellar-agent-escrow
cargo build --target wasm32v1-none --release

# Run tests
cargo test
```

### 2. Developer Dashboard (React)

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:5173
```

### 3. Agent SDK (Python)

```bash
cd agent-sdk
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run the E2E demo
python ../demo-merchant/e2e_demo.py
```

### 4. Demo Merchant Server

```bash
cd demo-merchant
python server.py
# Merchant runs on http://localhost:8402
```

## ⚡ How It Works

```
Agent → Request Data → Merchant API
                         ↓ HTTP 402
Agent SDK ← Payment Challenge (address, amount)
    ↓
Soroban Escrow Contract
    ↓ Validates limits → Transfers USDC
Agent SDK → Retry with TX hash → Merchant API
                                    ↓ Verify TX
                              ← HTTP 200 + Data
```

## 📋 Phase 1 Deliverables (Complete ✅)

| Component | Status | Description |
|-----------|--------|-------------|
| Escrow Contract | ✅ | Soroban smart contract with deposits, spending limits, merchant whitelists |
| Unit Tests | ✅ | 18+ tests covering all escrow scenarios |
| Developer Dashboard | ✅ | React app with agent management, deposits, transaction view |
| Agent SDK | ✅ | Python SDK with x402 interceptor and spending validation |
| Demo Merchant | ✅ | HTTP 402 server simulating paywalled API |
| E2E Demo | ✅ | End-to-end testnet payment flow demonstration |

## 🔑 Key Features

- **Programmable Spending Limits** — Set daily and per-transaction caps for each agent
- **Merchant Whitelisting** — Control which APIs your agents can pay
- **x402 Auto-Payment** — SDK automatically handles HTTP 402 challenges
- **Daily Limit Reset** — Spending limits reset every 24 hours
- **Agent Lifecycle** — Activate, pause, and manage agents from the dashboard

## 📄 License

Apache-2.0
