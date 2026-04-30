#![cfg(test)]

use soroban_sdk::{
    testutils::{Address as _, Ledger, LedgerInfo},
    token, Address, Env, Vec,
};

use crate::escrow::{EscrowContract, EscrowContractClient};
use crate::types::AgentConfig;

/// Helper: create a test environment with the contract deployed and initialized
fn setup_test() -> (Env, EscrowContractClient<'static>, Address, Address, Address) {
    let env = Env::default();
    env.mock_all_auths();

    // Set initial ledger timestamp
    env.ledger().set(LedgerInfo {
        timestamp: 1_000_000,
        protocol_version: 22,
        sequence_number: 100,
        network_id: Default::default(),
        base_reserve: 10,
        min_temp_entry_ttl: 10,
        min_persistent_entry_ttl: 10,
        max_entry_ttl: 3_110_400,
    });

    let contract_id = env.register(EscrowContract, ());
    let client = EscrowContractClient::new(&env, &contract_id);

    let admin = Address::generate(&env);

    // Create a test token (mock USDC)
    let token_admin = Address::generate(&env);
    let token_contract = env.register_stellar_asset_contract_v2(token_admin.clone());
    let token_id = token_contract.address();
    let token_admin_client = token::StellarAssetClient::new(&env, &token_id);

    // Initialize escrow
    client.initialize(&admin, &token_id);

    // Create a developer and mint them tokens
    let developer = Address::generate(&env);
    token_admin_client.mint(&developer, &100_000_000_000); // 100,000 USDC (7 decimals)

    (env, client, admin, developer, token_id)
}

// ──────────────────────────────────────────────────
// Test: Initialization
// ──────────────────────────────────────────────────

#[test]
fn test_initialize() {
    let (env, client, _admin, _developer, _token_id) = setup_test();
    assert_eq!(client.get_tx_count(), 0);
}

#[test]
#[should_panic(expected = "already initialized")]
fn test_initialize_twice_fails() {
    let (env, client, admin, _developer, token_id) = setup_test();
    client.initialize(&admin, &token_id);
}

// ──────────────────────────────────────────────────
// Test: Deposits & Withdrawals
// ──────────────────────────────────────────────────

#[test]
fn test_deposit() {
    let (_env, client, _admin, developer, _token_id) = setup_test();

    client.deposit(&developer, &10_000_000_000); // 10,000 USDC
    assert_eq!(client.get_balance(&developer), 10_000_000_000);
}

#[test]
fn test_deposit_multiple() {
    let (_env, client, _admin, developer, _token_id) = setup_test();

    client.deposit(&developer, &5_000_000_000);
    client.deposit(&developer, &3_000_000_000);
    assert_eq!(client.get_balance(&developer), 8_000_000_000);
}

#[test]
#[should_panic(expected = "deposit amount must be positive")]
fn test_deposit_zero_fails() {
    let (_env, client, _admin, developer, _token_id) = setup_test();
    client.deposit(&developer, &0);
}

#[test]
fn test_withdraw() {
    let (_env, client, _admin, developer, _token_id) = setup_test();

    client.deposit(&developer, &10_000_000_000);
    client.withdraw(&developer, &3_000_000_000);
    assert_eq!(client.get_balance(&developer), 7_000_000_000);
}

#[test]
#[should_panic(expected = "insufficient escrow balance")]
fn test_withdraw_exceeds_balance() {
    let (_env, client, _admin, developer, _token_id) = setup_test();

    client.deposit(&developer, &1_000_000_000);
    client.withdraw(&developer, &2_000_000_000);
}

// ──────────────────────────────────────────────────
// Test: Agent Registration
// ──────────────────────────────────────────────────

#[test]
fn test_register_agent() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    client.register_agent(
        &developer,
        &agent,
        &5_000_000_000, // 5000 USDC daily
        &1_000_000_000, // 1000 USDC per tx
    );

    let config = client.get_agent_config(&agent);
    assert_eq!(config.daily_limit, 5_000_000_000);
    assert_eq!(config.per_tx_limit, 1_000_000_000);
    assert!(config.is_active);

    let agents = client.get_dev_agents(&developer);
    assert_eq!(agents.len(), 1);
}

#[test]
#[should_panic(expected = "agent already registered")]
fn test_register_agent_duplicate_fails() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);
}

#[test]
#[should_panic(expected = "per-tx limit cannot exceed daily limit")]
fn test_register_agent_bad_limits() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    client.register_agent(
        &developer,
        &agent,
        &1_000_000_000,  // daily < per_tx
        &5_000_000_000,
    );
}

// ──────────────────────────────────────────────────
// Test: Agent Activation / Deactivation
// ──────────────────────────────────────────────────

#[test]
fn test_deactivate_and_activate_agent() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    // Deactivate
    client.deactivate_agent(&developer, &agent);
    let config = client.get_agent_config(&agent);
    assert!(!config.is_active);

    // Reactivate
    client.activate_agent(&developer, &agent);
    let config = client.get_agent_config(&agent);
    assert!(config.is_active);
}

// ──────────────────────────────────────────────────
// Test: Payments
// ──────────────────────────────────────────────────

#[test]
fn test_successful_payment() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    // Deposit and register agent
    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    // Execute payment
    let tx_id = client.pay(&agent, &merchant, &500_000_000); // 500 USDC
    assert_eq!(tx_id, 1);

    // Check updated balance
    assert_eq!(client.get_balance(&developer), 9_500_000_000);

    // Check daily spend
    let spend = client.get_daily_spend(&agent);
    assert_eq!(spend.amount, 500_000_000);

    // Tx count should be 1
    assert_eq!(client.get_tx_count(), 1);
}

#[test]
fn test_multiple_payments() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    client.pay(&agent, &merchant, &100_000_000);
    client.pay(&agent, &merchant, &200_000_000);
    let tx_id = client.pay(&agent, &merchant, &300_000_000);

    assert_eq!(tx_id, 3);
    assert_eq!(client.get_balance(&developer), 9_400_000_000);

    let spend = client.get_daily_spend(&agent);
    assert_eq!(spend.amount, 600_000_000);
}

#[test]
#[should_panic(expected = "amount exceeds per-transaction limit")]
fn test_payment_exceeds_per_tx_limit() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    // Try to pay more than per-tx limit
    client.pay(&agent, &merchant, &2_000_000_000);
}

#[test]
#[should_panic(expected = "amount exceeds daily spending limit")]
fn test_payment_exceeds_daily_limit() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &2_000_000_000, &1_000_000_000);

    // Two payments of 1000 each = 2000, then try another
    client.pay(&agent, &merchant, &1_000_000_000);
    client.pay(&agent, &merchant, &1_000_000_000);
    client.pay(&agent, &merchant, &500_000_000); // Exceeds daily
}

#[test]
fn test_daily_limit_resets_after_day() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &50_000_000_000);
    client.register_agent(&developer, &agent, &2_000_000_000, &1_000_000_000);

    // Spend up to daily limit
    client.pay(&agent, &merchant, &1_000_000_000);
    client.pay(&agent, &merchant, &1_000_000_000);

    // Advance time by 1 day + 1 second
    env.ledger().set(LedgerInfo {
        timestamp: 1_000_000 + 86_401,
        protocol_version: 22,
        sequence_number: 200,
        network_id: Default::default(),
        base_reserve: 10,
        min_temp_entry_ttl: 10,
        min_persistent_entry_ttl: 10,
        max_entry_ttl: 3_110_400,
    });

    // Should succeed now — daily limit reset
    client.pay(&agent, &merchant, &1_000_000_000);
    let spend = client.get_daily_spend(&agent);
    assert_eq!(spend.amount, 1_000_000_000);
}

#[test]
#[should_panic(expected = "agent is deactivated")]
fn test_payment_from_deactivated_agent() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);
    client.deactivate_agent(&developer, &agent);

    client.pay(&agent, &merchant, &100_000_000);
}

#[test]
#[should_panic(expected = "insufficient developer escrow balance")]
fn test_payment_insufficient_balance() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &100_000_000); // Only 100 USDC
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    client.pay(&agent, &merchant, &500_000_000); // Try to pay 500
}

// ──────────────────────────────────────────────────
// Test: Merchant Whitelist
// ──────────────────────────────────────────────────

#[test]
fn test_merchant_whitelist_allows() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    // Set whitelist with the merchant
    let mut whitelist = Vec::new(&env);
    whitelist.push_back(merchant.clone());
    client.set_merchant_whitelist(&developer, &agent, &whitelist);

    // Should succeed
    client.pay(&agent, &merchant, &100_000_000);
}

#[test]
#[should_panic(expected = "merchant not in agent whitelist")]
fn test_merchant_whitelist_blocks() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    let merchant_a = Address::generate(&env);
    let merchant_b = Address::generate(&env);

    client.deposit(&developer, &10_000_000_000);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    // Whitelist only merchant_a
    let mut whitelist = Vec::new(&env);
    whitelist.push_back(merchant_a.clone());
    client.set_merchant_whitelist(&developer, &agent, &whitelist);

    // Trying to pay merchant_b should fail
    client.pay(&agent, &merchant_b, &100_000_000);
}

// ──────────────────────────────────────────────────
// Test: Update Limits
// ──────────────────────────────────────────────────

#[test]
fn test_update_agent_limits() {
    let (env, client, _admin, developer, _token_id) = setup_test();

    let agent = Address::generate(&env);
    client.register_agent(&developer, &agent, &5_000_000_000, &1_000_000_000);

    client.update_agent_limits(&developer, &agent, &10_000_000_000, &2_000_000_000);

    let config = client.get_agent_config(&agent);
    assert_eq!(config.daily_limit, 10_000_000_000);
    assert_eq!(config.per_tx_limit, 2_000_000_000);
}
