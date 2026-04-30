# System Architecture: StellarAgent Portal

## 1. High-Level Architecture Overview
The StellarAgent system acts as a middleware and financial gateway connecting AI Agents, the Stellar Blockchain (Soroban), and Web API Service Providers. 

## 2. Core Components

### A. AI Agent Client SDK (Python/Node.js)
A lightweight SDK installed in the AI agent's runtime environment (e.g., LangChain or AutoGPT extension).
* **Responsibilities:** * Listen for HTTP 402 (Payment Required) status codes.
    * Construct transaction envelopes.
    * Sign transactions using the agent's derived session key.
    * Forward signed transactions to the Escrow Backend.

### B. StellarAgent Backend Node (Rust / Node.js)
The core operational server managing off-chain logic and transaction submission.
* **Components:**
    * **x402 Relayer:** Intercepts payment requests, validates them against the agent's limits, and submits them to Stellar RPC.
    * **Reputation Engine:** Indexes on-chain history to calculate the agent's trust score.

### C. Stellar Blockchain (Soroban Smart Contracts)
The decentralized execution and settlement layer.
* **Escrow Contract (Rust):**
    * Holds the developer's USDC deposit.
    * Maintains state of allowances, daily limits, and authorized merchant lists.
    * Executes transfers only if the transaction signature matches the agent and the amount is within limits.
* **Identity Registry (Stellar 8004 Standard):**
    * Maps Agent Public Keys to their metadata (Creator KYC hash, creation date, reputation score).

### D. Service Providers (Merchants)
External APIs (Cloudflare, OpenAI, weather data) that accept x402 headers. They verify the Stellar transaction hash before serving the requested data.

## 3. Data Flow: "Pay-per-Crawl" Execution

1.  **Request:** AI Agent requests data from `api.merchant.com/data`.
2.  **Challenge:** Merchant responds with `HTTP 402 Payment Required`, including a Stellar destination address and amount (e.g., 0.001 USDC).
3.  **Evaluate:** Agent Client SDK intercepts the 402. It requests payment authorization from the Soroban Escrow Contract.
4.  **Validate:** Soroban contract checks if `0.001 USDC < Daily_Limit`.
5.  **Execute:** If valid, Soroban transfers 0.001 USDC to the Merchant's Stellar address using sub-cent fees.
6.  **Verify:** Transaction hash is returned to the Agent, which replays the original API request with the hash in the `Authorization: x402 <hash>` header.
7.  **Fulfill:** Merchant verifies the hash via Stellar RPC and serves the data.

## 4. Security Considerations
* **Agent Key Compromise:** Agents only hold session keys with strict Soroban-enforced spending limits. Master funds remain safe.
* **Replay Attacks:** All x402 transactions use Stellar's native sequence numbers to prevent replay attacks.
