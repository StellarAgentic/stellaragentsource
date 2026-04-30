import { useState, useCallback, useEffect } from 'react'
import './index.css'

// ═══════════════════════════════════════════════════
// Mock Data (simulates Soroban contract state on testnet)
// ═══════════════════════════════════════════════════

const MOCK_AGENTS = [
  {
    id: 'GAGENT_WEB_CRAWLER_01_ABCDEF1234',
    name: 'Web Crawler Alpha',
    dailyLimit: 5.0,
    perTxLimit: 0.5,
    dailySpent: 2.34,
    isActive: true,
    createdAt: '2026-04-28T10:30:00Z',
    txCount: 147,
  },
  {
    id: 'GAGENT_DATA_MINER_02_GHIJKL5678',
    name: 'Data Miner Beta',
    dailyLimit: 10.0,
    perTxLimit: 1.0,
    dailySpent: 6.78,
    isActive: true,
    createdAt: '2026-04-25T14:00:00Z',
    txCount: 892,
  },
  {
    id: 'GAGENT_API_CALLER_03_MNOPQR9012',
    name: 'API Caller Gamma',
    dailyLimit: 2.0,
    perTxLimit: 0.1,
    dailySpent: 0,
    isActive: false,
    createdAt: '2026-04-29T09:15:00Z',
    txCount: 23,
  },
]

const MOCK_TRANSACTIONS = [
  { id: 1, agent: 'Web Crawler Alpha', merchant: 'GMERCH_CLOUD...', amount: 0.001, status: 'success', hash: 'a1b2c3d4e5f6...', time: '2 min ago' },
  { id: 2, agent: 'Data Miner Beta', merchant: 'GMERCH_API_P...', amount: 0.005, status: 'success', hash: 'f6e5d4c3b2a1...', time: '5 min ago' },
  { id: 3, agent: 'Web Crawler Alpha', merchant: 'GMERCH_DATA_...', amount: 0.002, status: 'success', hash: '1a2b3c4d5e6f...', time: '8 min ago' },
  { id: 4, agent: 'Data Miner Beta', merchant: 'GMERCH_CLOUD...', amount: 0.010, status: 'success', hash: '6f5e4d3c2b1a...', time: '12 min ago' },
  { id: 5, agent: 'Web Crawler Alpha', merchant: 'GMERCH_WEATH...', amount: 0.001, status: 'pending', hash: 'pending...', time: '15 min ago' },
]

// ═══════════════════════════════════════════════════
// Helper Components
// ═══════════════════════════════════════════════════

function StatCard({ icon, label, value, change, changeType, color }) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${color}`}>{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {change && (
        <span className={`stat-change ${changeType}`}>{change}</span>
      )}
    </div>
  )
}

function Badge({ type, children }) {
  return <span className={`badge badge-${type}`}>{children}</span>
}

function ProgressBar({ value, max, label }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <div className="progress-label">
        <span>${value.toFixed(2)} spent</span>
        <span>${max.toFixed(2)} limit</span>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════
// Modal Components
// ═══════════════════════════════════════════════════

function DepositModal({ isOpen, onClose, onDeposit }) {
  const [amount, setAmount] = useState('')

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    onDeposit(parseFloat(amount))
    setAmount('')
    onClose()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2 className="modal-title">💰 Deposit USDC to Escrow</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Amount (USDC)</label>
            <input
              id="deposit-amount"
              type="number"
              className="form-input"
              placeholder="Enter amount to deposit..."
              value={amount}
              onChange={e => setAmount(e.target.value)}
              step="0.01"
              min="0.01"
              required
            />
            <div className="form-hint">Deposit USDC into your Soroban escrow contract on Stellar Testnet</div>
          </div>
          <div className="form-group">
            <label className="form-label">Network</label>
            <input className="form-input" value="Stellar Testnet" readOnly />
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" id="confirm-deposit">⚡ Deposit</button>
          </div>
        </form>
      </div>
    </div>
  )
}

function RegisterAgentModal({ isOpen, onClose, onRegister }) {
  const [name, setName] = useState('')
  const [dailyLimit, setDailyLimit] = useState('5.00')
  const [perTxLimit, setPerTxLimit] = useState('1.00')

  if (!isOpen) return null

  const handleSubmit = (e) => {
    e.preventDefault()
    onRegister({ name, dailyLimit: parseFloat(dailyLimit), perTxLimit: parseFloat(perTxLimit) })
    setName('')
    setDailyLimit('5.00')
    setPerTxLimit('1.00')
    onClose()
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h2 className="modal-title">🤖 Register New Agent</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Agent Name</label>
            <input
              id="agent-name"
              className="form-input"
              placeholder="e.g., Web Crawler Alpha"
              value={name}
              onChange={e => setName(e.target.value)}
              required
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Daily Limit (USDC)</label>
              <input
                id="agent-daily-limit"
                type="number"
                className="form-input"
                value={dailyLimit}
                onChange={e => setDailyLimit(e.target.value)}
                step="0.01"
                min="0.01"
                required
              />
              <div className="form-hint">Max spend per 24h</div>
            </div>
            <div className="form-group">
              <label className="form-label">Per-TX Limit (USDC)</label>
              <input
                id="agent-per-tx-limit"
                type="number"
                className="form-input"
                value={perTxLimit}
                onChange={e => setPerTxLimit(e.target.value)}
                step="0.01"
                min="0.01"
                required
              />
              <div className="form-hint">Max per transaction</div>
            </div>
          </div>
          <div className="modal-actions">
            <button type="button" className="btn btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn btn-primary" id="confirm-register">🚀 Register Agent</button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ═══════════════════════════════════════════════════
// Page Views
// ═══════════════════════════════════════════════════

function OverviewPage({ balance, agents, transactions, onOpenDeposit }) {
  const totalDailySpent = agents.reduce((sum, a) => sum + a.dailySpent, 0)
  const activeAgents = agents.filter(a => a.isActive).length
  const totalTx = agents.reduce((sum, a) => sum + a.txCount, 0)

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Dashboard Overview</h1>
        <p className="page-subtitle">Monitor your AI agents and escrow balance on Stellar Testnet</p>
      </div>

      <div className="stats-grid">
        <StatCard icon="💎" label="Escrow Balance" value={`$${balance.toFixed(2)}`} change="Testnet USDC" changeType="positive" color="blue" />
        <StatCard icon="🤖" label="Active Agents" value={`${activeAgents}/${agents.length}`} change={`${activeAgents} running`} changeType="positive" color="purple" />
        <StatCard icon="⚡" label="Today's Spend" value={`$${totalDailySpent.toFixed(2)}`} color="cyan" />
        <StatCard icon="📊" label="Total Transactions" value={totalTx.toLocaleString()} change="+47 today" changeType="positive" color="green" />
      </div>

      <div className="content-grid">
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Escrow Funding</div>
              <div className="card-subtitle">Manage your testnet USDC deposit</div>
            </div>
            <button className="btn btn-primary btn-sm" onClick={onOpenDeposit} id="deposit-btn">
              💰 Deposit
            </button>
          </div>
          <div className="flex flex-col gap-md">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted">Contract Address</span>
              <span className="text-mono text-sm text-accent">CESCROW...XYZ7</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted">Network</span>
              <Badge type="testnet">Testnet</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted">Token</span>
              <span className="text-sm">USDC (Stellar)</span>
            </div>
            <div className="mt-md">
              <ProgressBar value={totalDailySpent} max={balance} />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Recent Activity</div>
              <div className="card-subtitle">Latest agent transactions</div>
            </div>
          </div>
          <div className="tx-feed">
            {transactions.slice(0, 4).map(tx => (
              <div key={tx.id} className="tx-item">
                <div className={`tx-icon ${tx.status}`}>
                  {tx.status === 'success' ? '✅' : '⏳'}
                </div>
                <div className="tx-details">
                  <div className="tx-description">{tx.agent} → {tx.merchant}</div>
                  <div className="tx-meta">{tx.hash} · {tx.time}</div>
                </div>
                <div className="tx-amount debit">-${tx.amount.toFixed(4)}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  )
}

function AgentsPage({ agents, setAgents, onOpenRegister }) {
  const toggleAgent = (index) => {
    const updated = [...agents]
    updated[index] = { ...updated[index], isActive: !updated[index].isActive }
    setAgents(updated)
  }

  return (
    <>
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="page-title">AI Agents</h1>
          <p className="page-subtitle">Manage registered agents and their spending limits</p>
        </div>
        <button className="btn btn-primary" onClick={onOpenRegister} id="register-agent-btn">
          🤖 Register Agent
        </button>
      </div>

      <div className="card">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Status</th>
                <th>Daily Limit</th>
                <th>Daily Spent</th>
                <th>Per-TX Limit</th>
                <th>Transactions</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent, i) => (
                <tr key={agent.id}>
                  <td>
                    <div style={{ fontWeight: 600, color: 'var(--color-text-primary)' }}>{agent.name}</div>
                    <div className="text-mono" style={{ fontSize: 11, color: 'var(--color-text-muted)' }}>
                      {agent.id.slice(0, 16)}...
                    </div>
                  </td>
                  <td>
                    {agent.isActive ? (
                      <Badge type="active"><span className="pulse-dot" style={{ display: 'inline-block', width: 6, height: 6 }} /> Active</Badge>
                    ) : (
                      <Badge type="inactive">Paused</Badge>
                    )}
                  </td>
                  <td>${agent.dailyLimit.toFixed(2)}</td>
                  <td>
                    <ProgressBar value={agent.dailySpent} max={agent.dailyLimit} />
                  </td>
                  <td>${agent.perTxLimit.toFixed(2)}</td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>{agent.txCount}</td>
                  <td>
                    <div className="flex gap-sm">
                      <button
                        className={`btn btn-sm ${agent.isActive ? 'btn-danger' : 'btn-primary'}`}
                        onClick={() => toggleAgent(i)}
                        id={`toggle-agent-${i}`}
                      >
                        {agent.isActive ? '⏸ Pause' : '▶ Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function TransactionsPage({ transactions }) {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Transactions</h1>
        <p className="page-subtitle">All agent payment transactions on Stellar Testnet</p>
      </div>

      <div className="card">
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Agent</th>
                <th>Merchant</th>
                <th>Amount</th>
                <th>Status</th>
                <th>TX Hash</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map(tx => (
                <tr key={tx.id}>
                  <td>#{tx.id}</td>
                  <td style={{ fontWeight: 500 }}>{tx.agent}</td>
                  <td className="mono">{tx.merchant}</td>
                  <td className="tx-amount debit">-${tx.amount.toFixed(4)}</td>
                  <td>
                    <Badge type={tx.status === 'success' ? 'active' : 'pending'}>
                      {tx.status === 'success' ? '✅ Success' : '⏳ Pending'}
                    </Badge>
                  </td>
                  <td className="mono" style={{ fontSize: 12 }}>{tx.hash}</td>
                  <td className="text-muted">{tx.time}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}

function SettingsPage() {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure your StellarAgent deployment</p>
      </div>

      <div className="content-grid">
        <div className="card">
          <div className="card-title mb-md">Network Configuration</div>
          <div className="form-group">
            <label className="form-label">Stellar Network</label>
            <input className="form-input" value="Testnet" readOnly />
          </div>
          <div className="form-group">
            <label className="form-label">Soroban RPC URL</label>
            <input className="form-input mono" value="https://soroban-testnet.stellar.org" readOnly />
          </div>
          <div className="form-group">
            <label className="form-label">Escrow Contract ID</label>
            <input className="form-input mono" value="CESCROW_CONTRACT_TESTNET_ADDR" readOnly />
          </div>
        </div>

        <div className="card">
          <div className="card-title mb-md">Wallet Connection</div>
          <div className="form-group">
            <label className="form-label">Connected Wallet</label>
            <input className="form-input mono" value="GDEVELOPER_PUBLIC_KEY..." readOnly />
          </div>
          <div className="form-group">
            <label className="form-label">Wallet Provider</label>
            <input className="form-input" value="Freighter" readOnly />
          </div>
          <div className="mt-lg">
            <button className="btn btn-secondary" id="reconnect-wallet">🔗 Reconnect Wallet</button>
          </div>
        </div>
      </div>
    </>
  )
}

// ═══════════════════════════════════════════════════
// Main App
// ═══════════════════════════════════════════════════

function App() {
  const [page, setPage] = useState('overview')
  const [balance, setBalance] = useState(1250.00)
  const [agents, setAgents] = useState(MOCK_AGENTS)
  const [transactions] = useState(MOCK_TRANSACTIONS)
  const [showDeposit, setShowDeposit] = useState(false)
  const [showRegister, setShowRegister] = useState(false)

  const handleDeposit = useCallback((amount) => {
    setBalance(prev => prev + amount)
  }, [])

  const handleRegister = useCallback((data) => {
    const newAgent = {
      id: `GAGENT_${data.name.replace(/\s+/g, '_').toUpperCase()}_${Date.now()}`,
      name: data.name,
      dailyLimit: data.dailyLimit,
      perTxLimit: data.perTxLimit,
      dailySpent: 0,
      isActive: true,
      createdAt: new Date().toISOString(),
      txCount: 0,
    }
    setAgents(prev => [...prev, newAgent])
  }, [])

  const navItems = [
    { id: 'overview', icon: '📊', label: 'Overview' },
    { id: 'agents', icon: '🤖', label: 'Agents' },
    { id: 'transactions', icon: '⚡', label: 'Transactions' },
    { id: 'settings', icon: '⚙️', label: 'Settings' },
  ]

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="logo">
          <div className="logo-icon">⚡</div>
          <div>
            <div className="logo-text">StellarAgent</div>
          </div>
          <span className="logo-badge">v0.1</span>
        </div>

        <nav className="nav-section">
          <div className="nav-section-title">Main</div>
          {navItems.map(item => (
            <div
              key={item.id}
              className={`nav-item ${page === item.id ? 'active' : ''}`}
              onClick={() => setPage(item.id)}
              id={`nav-${item.id}`}
            >
              <span className="nav-item-icon">{item.icon}</span>
              <span>{item.label}</span>
            </div>
          ))}
        </nav>

        <div style={{ marginTop: 'auto' }}>
          <div className="nav-section-title">Network</div>
          <div className="flex items-center gap-sm" style={{ padding: '8px 12px' }}>
            <span className="pulse-dot" />
            <span className="text-sm">Stellar Testnet</span>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {page === 'overview' && (
          <OverviewPage
            balance={balance}
            agents={agents}
            transactions={transactions}
            onOpenDeposit={() => setShowDeposit(true)}
          />
        )}
        {page === 'agents' && (
          <AgentsPage
            agents={agents}
            setAgents={setAgents}
            onOpenRegister={() => setShowRegister(true)}
          />
        )}
        {page === 'transactions' && <TransactionsPage transactions={transactions} />}
        {page === 'settings' && <SettingsPage />}
      </main>

      {/* Modals */}
      <DepositModal
        isOpen={showDeposit}
        onClose={() => setShowDeposit(false)}
        onDeposit={handleDeposit}
      />
      <RegisterAgentModal
        isOpen={showRegister}
        onClose={() => setShowRegister(false)}
        onRegister={handleRegister}
      />
    </div>
  )
}

export default App
