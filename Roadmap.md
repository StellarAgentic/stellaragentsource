# Project Roadmap: StellarAgent

## Phase 1: Foundation & Proof of Concept (Months 1-2)
**Goal:** Build the basic Soroban escrow mechanics and UI.
* [x] Define Soroban Smart Contract architecture for Escrow and Spending Limits.
* [x] Write and unit-test the Escrow Contract in Rust.
* [x] Develop the Developer Dashboard (React) for depositing testnet USDC.
* [x] Create a basic Agent SDK to trigger payments.
* [x] **Milestone:** End-to-end testnet transaction where an agent pays for a mocked API call within its allowance.

## Phase 2: Protocol Integration & Identity (Months 3-4)
**Goal:** Implement 2026 Stellar standards (8004 and x402).
* [ ] Integrate Stellar 8004 Standard: Deploy the Identity Registry contract.
* [ ] Mint Agent IDs upon creation in the dashboard.
* [ ] Implement the x402 Machine Payment Protocol interceptor in the Agent SDK.
* [ ] Build a demo Merchant Server that enforces HTTP 402 and validates Stellar transaction hashes.
* [ ] **Milestone:** Successful deployment of Identity and Escrow contracts to Stellar Testnet.

## Phase 3: Reputation & Advanced Features (Months 5-6)
**Goal:** Enable autonomous negotiation and privacy.
* [ ] Build the off-chain Reputation Engine (indexing agent successful payments and age).
* [ ] Integrate Protocol 25/26 ZK-proof features to shield the developer's master escrow balance from public view.
* [ ] Create an SDK module that allows agents to present their ZK-identity and Reputation Score to merchants for rate negotiation.
* [ ] **Milestone:** Comprehensive Security Audit of Soroban contracts.

## Phase 4: Mainnet Launch & Ecosystem Expansion (Months 7-8)
**Goal:** Go live and onboard the first wave of agents and merchants.
* [ ] Deploy contracts to Stellar Mainnet.
* [ ] Launch marketing campaign targeting AI developers and Web3 infrastructure builders.
* [ ] Partner with a major API provider (e.g., decentralized RPC node provider) to accept StellarAgent natively.
* [ ] **Milestone:** 100 active AI agents funded and operating on Mainnet.

## Phase 5: Governance & Yield (Months 9+)
**Goal:** Maximize capital efficiency.
* [ ] Integrate with Stellar DeFi lending protocols (e.g., Blend).
* [ ] Allow idle USDC in developer escrows to earn yield in tokenized Treasuries while waiting to be spent by agents.
* [ ] Transition control of protocol parameters to a DAO structure.
