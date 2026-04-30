use soroban_sdk::{contracttype, Address, Vec};

/// Storage keys for the escrow contract
#[derive(Clone)]
#[contracttype]
pub enum DataKey {
    /// Admin address that initialized the contract
    Admin,
    /// Token contract address (e.g. USDC)
    TokenId,
    /// Developer deposit balance: Developer Address -> Balance (i128)
    DevBalance(Address),
    /// Agent configuration: Agent Address -> AgentConfig
    AgentConfig(Address),
    /// Agent's daily spend tracking: Agent Address -> DailySpend
    DailySpend(Address),
    /// Mapping from Agent -> Developer who owns it
    AgentOwner(Address),
    /// List of agents for a developer: Developer Address -> Vec<Address>
    DevAgents(Address),
    /// Whitelisted merchants for an agent: Agent Address -> Vec<Address>
    AgentMerchants(Address),
    /// Total number of transactions processed
    TxCount,
}

/// Configuration for an AI agent's spending capabilities
#[derive(Clone, Debug, PartialEq)]
#[contracttype]
pub struct AgentConfig {
    /// Maximum amount the agent can spend per day (in token smallest units)
    pub daily_limit: i128,
    /// Maximum amount the agent can spend per single transaction
    pub per_tx_limit: i128,
    /// Whether the agent is currently active
    pub is_active: bool,
    /// Timestamp when the agent was created
    pub created_at: u64,
}

/// Tracks an agent's daily spending for rate limiting
#[derive(Clone, Debug, PartialEq)]
#[contracttype]
pub struct DailySpend {
    /// Total amount spent in the current period
    pub amount: i128,
    /// Timestamp of the start of the current spending period (day boundary)
    pub period_start: u64,
}

/// Event emitted when a deposit is made
#[derive(Clone, Debug, PartialEq)]
#[contracttype]
pub struct DepositEvent {
    pub developer: Address,
    pub amount: i128,
}

/// Event emitted when a payment is executed
#[derive(Clone, Debug, PartialEq)]
#[contracttype]
pub struct PaymentEvent {
    pub agent: Address,
    pub merchant: Address,
    pub amount: i128,
    pub tx_id: u64,
}
