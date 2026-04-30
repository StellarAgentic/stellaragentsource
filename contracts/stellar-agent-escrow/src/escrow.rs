use soroban_sdk::{contract, contractimpl, token, Address, Env, Vec, log};

use crate::types::{AgentConfig, DailySpend, DataKey, DepositEvent, PaymentEvent};

/// One day in seconds (used for daily limit resets)
const DAY_IN_SECONDS: u64 = 86_400;

#[contract]
pub struct EscrowContract;

#[contractimpl]
impl EscrowContract {
    // ──────────────────────────────────────────────────
    // Initialization
    // ──────────────────────────────────────────────────

    /// Initialize the escrow contract with the admin and the token (USDC) address.
    /// Can only be called once.
    pub fn initialize(env: Env, admin: Address, token_id: Address) {
        // Ensure contract hasn't been initialized
        if env.storage().instance().has(&DataKey::Admin) {
            panic!("already initialized");
        }

        admin.require_auth();

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::TokenId, &token_id);
        env.storage().instance().set(&DataKey::TxCount, &0u64);

        log!(&env, "StellarAgent Escrow initialized by {}", admin);
    }

    // ──────────────────────────────────────────────────
    // Developer Operations
    // ──────────────────────────────────────────────────

    /// Developer deposits USDC into their escrow balance.
    /// The developer must have approved the token transfer beforehand.
    pub fn deposit(env: Env, developer: Address, amount: i128) {
        developer.require_auth();

        if amount <= 0 {
            panic!("deposit amount must be positive");
        }

        let token_id: Address = env.storage().instance().get(&DataKey::TokenId).unwrap();
        let token_client = token::Client::new(&env, &token_id);

        // Transfer tokens from developer to this contract
        token_client.transfer(
            &developer,
            &env.current_contract_address(),
            &amount,
        );

        // Update balance
        let key = DataKey::DevBalance(developer.clone());
        let current_balance: i128 = env.storage().persistent().get(&key).unwrap_or(0);
        let new_balance = current_balance + amount;
        env.storage().persistent().set(&key, &new_balance);

        env.events().publish(
            (symbol!("deposit"),),
            DepositEvent {
                developer,
                amount,
            },
        );
    }

    /// Developer withdraws USDC from their escrow balance.
    pub fn withdraw(env: Env, developer: Address, amount: i128) {
        developer.require_auth();

        if amount <= 0 {
            panic!("withdraw amount must be positive");
        }

        let key = DataKey::DevBalance(developer.clone());
        let current_balance: i128 = env.storage().persistent().get(&key).unwrap_or(0);

        if amount > current_balance {
            panic!("insufficient escrow balance");
        }

        let token_id: Address = env.storage().instance().get(&DataKey::TokenId).unwrap();
        let token_client = token::Client::new(&env, &token_id);

        // Transfer tokens back to developer
        token_client.transfer(
            &env.current_contract_address(),
            &developer,
            &amount,
        );

        let new_balance = current_balance - amount;
        env.storage().persistent().set(&key, &new_balance);
    }

    // ──────────────────────────────────────────────────
    // Agent Management
    // ──────────────────────────────────────────────────

    /// Register a new AI agent under a developer's account with spending limits.
    pub fn register_agent(
        env: Env,
        developer: Address,
        agent: Address,
        daily_limit: i128,
        per_tx_limit: i128,
    ) {
        developer.require_auth();

        if daily_limit <= 0 || per_tx_limit <= 0 {
            panic!("limits must be positive");
        }
        if per_tx_limit > daily_limit {
            panic!("per-tx limit cannot exceed daily limit");
        }

        // Check agent isn't already registered
        if env.storage().persistent().has(&DataKey::AgentConfig(agent.clone())) {
            panic!("agent already registered");
        }

        let config = AgentConfig {
            daily_limit,
            per_tx_limit,
            is_active: true,
            created_at: env.ledger().timestamp(),
        };

        env.storage().persistent().set(&DataKey::AgentConfig(agent.clone()), &config);
        env.storage().persistent().set(&DataKey::AgentOwner(agent.clone()), &developer);

        // Add to developer's agent list
        let agents_key = DataKey::DevAgents(developer.clone());
        let mut agents: Vec<Address> = env.storage().persistent().get(&agents_key).unwrap_or(Vec::new(&env));
        agents.push_back(agent.clone());
        env.storage().persistent().set(&agents_key, &agents);

        // Initialize daily spend tracker
        let daily_spend = DailySpend {
            amount: 0,
            period_start: env.ledger().timestamp(),
        };
        env.storage().persistent().set(&DataKey::DailySpend(agent.clone()), &daily_spend);

        log!(&env, "Agent {} registered under developer {}", agent, developer);
    }

    /// Developer updates the spending limits for one of their agents.
    pub fn update_agent_limits(
        env: Env,
        developer: Address,
        agent: Address,
        daily_limit: i128,
        per_tx_limit: i128,
    ) {
        developer.require_auth();
        Self::assert_agent_owner(&env, &agent, &developer);

        if daily_limit <= 0 || per_tx_limit <= 0 {
            panic!("limits must be positive");
        }
        if per_tx_limit > daily_limit {
            panic!("per-tx limit cannot exceed daily limit");
        }

        let mut config: AgentConfig = env
            .storage()
            .persistent()
            .get(&DataKey::AgentConfig(agent.clone()))
            .unwrap();

        config.daily_limit = daily_limit;
        config.per_tx_limit = per_tx_limit;

        env.storage().persistent().set(&DataKey::AgentConfig(agent.clone()), &config);
    }

    /// Developer deactivates an agent (pauses spending).
    pub fn deactivate_agent(env: Env, developer: Address, agent: Address) {
        developer.require_auth();
        Self::assert_agent_owner(&env, &agent, &developer);

        let mut config: AgentConfig = env
            .storage()
            .persistent()
            .get(&DataKey::AgentConfig(agent.clone()))
            .unwrap();

        config.is_active = false;
        env.storage().persistent().set(&DataKey::AgentConfig(agent.clone()), &config);
    }

    /// Developer reactivates an agent.
    pub fn activate_agent(env: Env, developer: Address, agent: Address) {
        developer.require_auth();
        Self::assert_agent_owner(&env, &agent, &developer);

        let mut config: AgentConfig = env
            .storage()
            .persistent()
            .get(&DataKey::AgentConfig(agent.clone()))
            .unwrap();

        config.is_active = true;
        env.storage().persistent().set(&DataKey::AgentConfig(agent.clone()), &config);
    }

    /// Developer sets a whitelist of allowed merchants for an agent.
    pub fn set_merchant_whitelist(
        env: Env,
        developer: Address,
        agent: Address,
        merchants: Vec<Address>,
    ) {
        developer.require_auth();
        Self::assert_agent_owner(&env, &agent, &developer);

        env.storage().persistent().set(&DataKey::AgentMerchants(agent), &merchants);
    }

    // ──────────────────────────────────────────────────
    // Payment Execution (called by agents / relayer)
    // ──────────────────────────────────────────────────

    /// Execute a payment from the developer's escrow on behalf of an agent.
    /// Validates the agent's spending limits before executing.
    /// Returns the transaction ID.
    pub fn pay(env: Env, agent: Address, merchant: Address, amount: i128) -> u64 {
        agent.require_auth();

        if amount <= 0 {
            panic!("payment amount must be positive");
        }

        // 1. Load agent config and verify it's active
        let config: AgentConfig = env
            .storage()
            .persistent()
            .get(&DataKey::AgentConfig(agent.clone()))
            .expect("agent not registered");

        if !config.is_active {
            panic!("agent is deactivated");
        }

        // 2. Check per-transaction limit
        if amount > config.per_tx_limit {
            panic!("amount exceeds per-transaction limit");
        }

        // 3. Check and update daily spend
        let daily_key = DataKey::DailySpend(agent.clone());
        let mut daily_spend: DailySpend = env
            .storage()
            .persistent()
            .get(&daily_key)
            .unwrap();

        let now = env.ledger().timestamp();
        // Reset if a new day
        if now - daily_spend.period_start >= DAY_IN_SECONDS {
            daily_spend.amount = 0;
            daily_spend.period_start = now;
        }

        if daily_spend.amount + amount > config.daily_limit {
            panic!("amount exceeds daily spending limit");
        }

        // 4. Check merchant whitelist (if configured)
        let merchants_key = DataKey::AgentMerchants(agent.clone());
        if env.storage().persistent().has(&merchants_key) {
            let whitelist: Vec<Address> = env.storage().persistent().get(&merchants_key).unwrap();
            if whitelist.len() > 0 {
                let mut found = false;
                for i in 0..whitelist.len() {
                    if whitelist.get(i).unwrap() == merchant {
                        found = true;
                        break;
                    }
                }
                if !found {
                    panic!("merchant not in agent whitelist");
                }
            }
        }

        // 5. Check developer has sufficient balance
        let owner: Address = env
            .storage()
            .persistent()
            .get(&DataKey::AgentOwner(agent.clone()))
            .unwrap();

        let balance_key = DataKey::DevBalance(owner.clone());
        let dev_balance: i128 = env.storage().persistent().get(&balance_key).unwrap_or(0);

        if dev_balance < amount {
            panic!("insufficient developer escrow balance");
        }

        // 6. Execute the transfer
        let token_id: Address = env.storage().instance().get(&DataKey::TokenId).unwrap();
        let token_client = token::Client::new(&env, &token_id);

        token_client.transfer(
            &env.current_contract_address(),
            &merchant,
            &amount,
        );

        // 7. Update state
        let new_dev_balance = dev_balance - amount;
        env.storage().persistent().set(&balance_key, &new_dev_balance);

        daily_spend.amount += amount;
        env.storage().persistent().set(&daily_key, &daily_spend);

        // 8. Increment and return tx ID
        let mut tx_count: u64 = env.storage().instance().get(&DataKey::TxCount).unwrap_or(0);
        tx_count += 1;
        env.storage().instance().set(&DataKey::TxCount, &tx_count);

        env.events().publish(
            (symbol!("payment"),),
            PaymentEvent {
                agent,
                merchant,
                amount,
                tx_id: tx_count,
            },
        );

        tx_count
    }

    // ──────────────────────────────────────────────────
    // Query Functions
    // ──────────────────────────────────────────────────

    /// Get a developer's escrow balance.
    pub fn get_balance(env: Env, developer: Address) -> i128 {
        env.storage()
            .persistent()
            .get(&DataKey::DevBalance(developer))
            .unwrap_or(0)
    }

    /// Get an agent's configuration.
    pub fn get_agent_config(env: Env, agent: Address) -> AgentConfig {
        env.storage()
            .persistent()
            .get(&DataKey::AgentConfig(agent))
            .expect("agent not found")
    }

    /// Get an agent's current daily spend.
    pub fn get_daily_spend(env: Env, agent: Address) -> DailySpend {
        env.storage()
            .persistent()
            .get(&DataKey::DailySpend(agent))
            .expect("agent not found")
    }

    /// Get the list of agents owned by a developer.
    pub fn get_dev_agents(env: Env, developer: Address) -> Vec<Address> {
        env.storage()
            .persistent()
            .get(&DataKey::DevAgents(developer))
            .unwrap_or(Vec::new(&env))
    }

    /// Get the total transaction count.
    pub fn get_tx_count(env: Env) -> u64 {
        env.storage().instance().get(&DataKey::TxCount).unwrap_or(0)
    }

    // ──────────────────────────────────────────────────
    // Internal Helpers
    // ──────────────────────────────────────────────────

    fn assert_agent_owner(env: &Env, agent: &Address, expected_owner: &Address) {
        let owner: Address = env
            .storage()
            .persistent()
            .get(&DataKey::AgentOwner(agent.clone()))
            .expect("agent not registered");

        if owner != *expected_owner {
            panic!("caller is not the agent owner");
        }
    }
}

// Needed for the symbol! macro
use soroban_sdk::symbol_short as symbol;
