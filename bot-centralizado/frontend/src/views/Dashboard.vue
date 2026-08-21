<template>
  <div class="dashboard">
    <header class="page-header">
      <div>
        <h1>Aurex Operations Dashboard</h1>
        <p class="text-muted">Read-only supervision for broker state, runtime safety, and strategy readiness.</p>
      </div>
      <div class="verdict" :class="store.councilVerdict === 'NO_GO_FOR_REAL_TRADING' ? 'verdict-danger' : 'verdict-warning'">
        <span class="verdict-label">Council verdict</span>
        <strong>{{ formatVerdict(store.councilVerdict) }}</strong>
      </div>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>Balance</span>
        <strong>{{ money(store.balance?.balance) }}</strong>
      </article>
      <article class="metric-card">
        <span>Available</span>
        <strong>{{ money(store.balance?.available) }}</strong>
      </article>
      <article class="metric-card">
        <span>Open P&amp;L</span>
        <strong :class="store.totalPnL >= 0 ? 'text-green' : 'text-red'">{{ signedMoney(store.totalPnL) }}</strong>
      </article>
      <article class="metric-card">
        <span>Positions</span>
        <strong>{{ store.positions.length }}</strong>
      </article>
    </section>

    <section class="panel-grid">
      <article class="panel panel-wide">
        <div class="panel-header">
          <h2>Runtime Gates</h2>
          <span class="badge badge-yellow">read-only</span>
        </div>
        <div class="gate-grid">
          <div v-for="gate in gates" :key="gate.name" class="gate-row">
            <span class="gate-dot" :class="`gate-${gate.status}`"></span>
            <div>
              <strong>{{ gate.name }}</strong>
              <p>{{ gate.detail }}</p>
            </div>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-header">
          <h2>API State</h2>
          <span class="badge" :class="store.wsConnected ? 'badge-green' : 'badge-gray'">
            {{ store.wsConnected ? 'connected' : 'offline' }}
          </span>
        </div>
        <dl class="kv-list">
          <div>
            <dt>Last refresh</dt>
            <dd>{{ formatDate(store.lastRefresh) }}</dd>
          </div>
          <div>
            <dt>Last price</dt>
            <dd>{{ store.livePrice?.price ? Number(store.livePrice.price).toFixed(2) : '-' }}</dd>
          </div>
          <div>
            <dt>Last error</dt>
            <dd>{{ store.lastError || '-' }}</dd>
          </div>
        </dl>
      </article>
    </section>

    <section class="panel-grid">
      <article class="panel">
        <div class="panel-header">
          <h2>Strategy Councils</h2>
        </div>
        <div class="strategy-list">
          <div v-for="strategy in strategies" :key="strategy.name" class="strategy-row">
            <div>
              <strong>{{ strategy.name }}</strong>
              <p>{{ strategy.description }}</p>
            </div>
            <span class="badge" :class="strategy.badgeClass">{{ strategy.mode }}</span>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-header">
          <h2>Positions</h2>
          <span class="badge badge-gray">{{ store.positions.length }}</span>
        </div>
        <div v-if="!store.positions.length" class="empty-state">
          No open positions detected.
        </div>
        <div v-else class="position-list">
          <div v-for="p in store.positions" :key="p.deal_id" class="position-row">
            <div>
              <strong>{{ p.epic }}</strong>
              <p>{{ p.direction }} x{{ p.size }}</p>
            </div>
            <span :class="(p.profit_loss || 0) >= 0 ? 'text-green' : 'text-red'">
              {{ signedMoney(p.profit_loss || 0) }}
            </span>
          </div>
        </div>
      </article>
    </section>

    <section class="panel">
      <div class="panel-header">
        <h2>Council Timeline</h2>
      </div>
      <div class="timeline">
        <div v-for="event in store.runtimeEvents" :key="event.label" class="timeline-row">
          <span class="gate-dot" :class="`gate-${event.status}`"></span>
          <div>
            <strong>{{ event.label }}</strong>
            <p>{{ event.detail }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useTradingStore } from '../stores/trading.js'

const store = useTradingStore()

const gates = computed(() => [
  {
    name: 'REAL broker mutation',
    status: 'blocked',
    detail: 'Requires CAPITAL_MODE=REAL, AUREX_ALLOW_REAL=YES, and AUREX_ALLOW_BROKER_MUTATION=YES.',
  },
  {
    name: 'Legacy runtime',
    status: 'blocked',
    detail: 'legacy/main.py, legacy/trader.py, and legacy/open_trade.py are disabled by default.',
  },
  {
    name: 'Safe sizing',
    status: 'running',
    detail: 'Broker minimum is not used if it would exceed the intended risk budget.',
  },
  {
    name: 'Live watch',
    status: 'running',
    detail: 'Council supervision is read-only and does not open, close, or modify trades.',
  },
])

const strategies = [
  {
    name: 'SWING',
    mode: 'guarded',
    badgeClass: 'badge-yellow',
    description: 'Daily GOLD strategy. Real execution requires explicit Council approval.',
  },
  {
    name: 'SCALP',
    mode: 'blocked',
    badgeClass: 'badge-red',
    description: 'Intraday path requires strategy-specific opt-in before any real execution.',
  },
  {
    name: 'M15',
    mode: 'paper',
    badgeClass: 'badge-gray',
    description: 'Observation-only while re-validation data is collected.',
  },
]

function money(value) {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-IE', { style: 'currency', currency: 'EUR' }).format(value)
}

function signedMoney(value) {
  if (value === null || value === undefined) return '-'
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${money(value)}`
}

function formatDate(value) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function formatVerdict(value) {
  return String(value || '').replaceAll('_', ' ')
}

onMounted(store.refreshReadOnly)
</script>

<style scoped>
.dashboard {
  display: grid;
  gap: 1rem;
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.page-header h1 {
  font-size: 24px;
  line-height: 1.2;
  margin-bottom: 0.25rem;
}

.verdict {
  min-width: 240px;
  border: 1px solid;
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
}

.verdict-label {
  display: block;
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  margin-bottom: 0.2rem;
}

.verdict-danger {
  background: rgba(248, 81, 73, 0.1);
  border-color: rgba(248, 81, 73, 0.45);
}

.verdict-warning {
  background: rgba(245, 158, 11, 0.1);
  border-color: rgba(245, 158, 11, 0.45);
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}

.metric-card,
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

.metric-card {
  padding: 1rem;
  display: grid;
  gap: 0.35rem;
}

.metric-card span {
  color: var(--muted);
  font-size: 12px;
}

.metric-card strong {
  font-size: 22px;
  font-family: var(--mono);
}

.panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(300px, 0.8fr);
  gap: 1rem;
}

.panel {
  padding: 1rem;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.9rem;
}

.panel-header h2 {
  font-size: 14px;
}

.gate-grid,
.strategy-list,
.position-list,
.timeline,
.kv-list {
  display: grid;
  gap: 0.75rem;
}

.gate-row,
.strategy-row,
.position-row,
.timeline-row,
.kv-list div {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.75rem;
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

.gate-row,
.timeline-row {
  justify-content: flex-start;
}

.gate-row p,
.strategy-row p,
.timeline-row p {
  color: var(--muted);
  margin-top: 0.15rem;
  font-size: 13px;
}

.gate-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-top: 0.3rem;
  flex: 0 0 auto;
}

.gate-running { background: var(--accent); }
.gate-blocked { background: var(--danger); }
.gate-warning { background: var(--warning); }

.kv-list dt {
  color: var(--muted);
  font-size: 12px;
}

.kv-list dd {
  font-family: var(--mono);
  text-align: right;
}

.empty-state {
  color: var(--muted);
  border-top: 1px solid var(--border);
  padding-top: 0.75rem;
}

@media (max-width: 980px) {
  .metrics-grid,
  .panel-grid {
    grid-template-columns: 1fr;
  }
}
</style>
