<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Dashboard</h1>
        <p class="text-muted">Estado en tiempo real de tu bot</p>
      </div>
      <div class="header-actions">
        <button v-if="!store.botRunning" class="btn btn-green" @click="handleStart" :disabled="starting">
          <span v-if="starting" class="spinner"></span>
          <span v-else>▶</span>
          Iniciar Bot
        </button>
        <button v-else class="btn btn-red" @click="handleStop">
          ■ Detener Bot
        </button>
      </div>
    </div>

    <!-- Balance cards -->
    <div class="grid-4" style="margin-bottom:1rem">
      <div class="card">
        <div class="card-label">Balance</div>
        <div class="card-value mono">
          {{ store.balance ? `€${store.balance.balance?.toFixed(2)}` : '—' }}
        </div>
      </div>
      <div class="card">
        <div class="card-label">Disponible</div>
        <div class="card-value mono">
          {{ store.balance ? `€${store.balance.available?.toFixed(2)}` : '—' }}
        </div>
      </div>
      <div class="card">
        <div class="card-label">P&L Abierto</div>
        <div class="card-value mono" :class="store.totalPnL >= 0 ? 'text-green' : 'text-red'">
          {{ store.totalPnL >= 0 ? '+' : '' }}€{{ store.totalPnL.toFixed(2) }}
        </div>
      </div>
      <div class="card">
        <div class="card-label">Posiciones</div>
        <div class="card-value mono">{{ store.positions.length }}</div>
      </div>
    </div>

    <!-- Bot config quick view -->
    <div class="card" style="margin-bottom:1rem">
      <div class="section-title">Configuración activa</div>
      <div class="config-row">
        <div class="form-group">
          <label>Activo</label>
          <select v-model="botConfig.epic">
            <option value="GOLD">GOLD (XAU/USD)</option>
            <option value="US30">US30 (Dow Jones)</option>
            <option value="US500">US500 (S&P 500)</option>
            <option value="US100">US100 (NASDAQ)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Timeframe</label>
          <select v-model="botConfig.timeframe">
            <option value="MINUTE_15">15 min (Intraday)</option>
            <option value="MINUTE_30">30 min (Intraday)</option>
            <option value="HOUR">1H (Intraday)</option>
            <option value="HOUR_4">4H (Swing)</option>
            <option value="DAY">1D (Swing)</option>
          </select>
        </div>
        <div class="form-group">
          <label>Riesgo por trade (%)</label>
          <input v-model.number="botConfig.risk_pct" type="number" step="0.1" min="0.5" max="5" />
        </div>
        <div class="form-group">
          <label>Intervalo check (seg)</label>
          <input v-model.number="botConfig.check_interval" type="number" step="300" min="300" />
        </div>
      </div>
      <div class="config-row" style="margin-top:0.75rem">
        <div class="form-group">
          <label>EMA Rápida</label>
          <input v-model.number="botConfig.ema_fast" type="number" />
        </div>
        <div class="form-group">
          <label>EMA Lenta</label>
          <input v-model.number="botConfig.ema_slow" type="number" />
        </div>
        <div class="form-group">
          <label>EMA Larga</label>
          <input v-model.number="botConfig.ema_long" type="number" />
        </div>
        <div class="form-group">
          <label>ATR SL mult</label>
          <input v-model.number="botConfig.atr_sl_mult" type="number" step="0.1" />
        </div>
        <div class="form-group">
          <label>ATR TP mult</label>
          <input v-model.number="botConfig.atr_tp_mult" type="number" step="0.1" />
        </div>
      </div>
    </div>

    <!-- Posiciones abiertas -->
    <div class="grid-2" style="margin-bottom:1rem">
      <div class="card">
        <div class="section-title">Posiciones abiertas</div>
        <div v-if="!store.positions.length" class="text-muted" style="padding:1rem 0">
          Sin posiciones abiertas
        </div>
        <div v-for="p in store.positions" :key="p.deal_id" class="position-card">
          <div class="position-header">
            <span class="mono">{{ p.epic }}</span>
            <span class="badge" :class="p.direction === 'BUY' ? 'badge-green' : 'badge-red'">
              {{ p.direction }}
            </span>
          </div>
          <div class="position-row">
            <span class="text-muted">Entrada</span>
            <span class="mono">{{ p.entry_price }}</span>
          </div>
          <div class="position-row">
            <span class="text-muted">SL / TP</span>
            <span class="mono text-red">{{ p.stop_loss }}</span>
            <span class="mono text-muted"> / </span>
            <span class="mono text-green">{{ p.take_profit }}</span>
          </div>
          <div class="position-row">
            <span class="text-muted">P&L</span>
            <span class="mono" :class="(p.profit_loss || 0) >= 0 ? 'text-green' : 'text-red'">
              {{ (p.profit_loss || 0) >= 0 ? '+' : '' }}€{{ (p.profit_loss || 0).toFixed(2) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Log de eventos -->
      <div class="card">
        <div class="section-title">Últimas operaciones del bot</div>
        <div v-if="!store.tradeLog.length" class="text-muted" style="padding:1rem 0">
          El bot no ha ejecutado operaciones aún
        </div>
        <div v-for="t in store.tradeLog.slice(0, 8)" :key="t.deal_id || t.timestamp" class="log-entry">
          <span class="badge" :class="t.direction === 'BUY' ? 'badge-green' : 'badge-red'" style="font-size:10px">
            {{ t.direction }}
          </span>
          <span class="mono">{{ t.epic }}</span>
          <span class="text-muted mono">@ {{ Number(t.entry_price).toFixed(2) }}</span>
          <span class="text-muted" style="font-size:11px; margin-left:auto">
            {{ t.timestamp ? new Date(t.timestamp).toLocaleTimeString('es') : '' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Live price -->
    <div v-if="store.livePrice" class="card">
      <div class="section-title">Precio en tiempo real</div>
      <div style="display:flex; gap:2rem; flex-wrap:wrap; padding-top:0.5rem">
        <div>
          <div class="card-label">Activo</div>
          <div class="card-value mono">{{ store.livePrice.epic }}</div>
        </div>
        <div>
          <div class="card-label">Precio</div>
          <div class="card-value mono">{{ Number(store.livePrice.price).toFixed(2) }}</div>
        </div>
        <div>
          <div class="card-label">Última revisión</div>
          <div class="card-value mono text-muted" style="font-size:13px">{{ store.livePrice.timestamp }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useTradingStore } from '../stores/trading.js'

const store = useTradingStore()
const starting = ref(false)

const botConfig = ref({
  epic: 'GOLD',
  timeframe: 'DAY',
  risk_pct: 1.5,
  max_positions: 2,
  check_interval: 3600,
  ema_fast: 8,
  ema_slow: 21,
  ema_long: 50,
  atr_sl_mult: 1.0,
  atr_tp_mult: 2.5,
})

async function handleStart() {
  starting.value = true
  await store.startBot(botConfig.value)
  starting.value = false
}

async function handleStop() {
  await store.stopBot()
}

onMounted(() => {
  store.fetchPositions()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  gap: 1rem;
}
.page-header h1 { font-size: 20px; font-weight: 700; }

.card-label { font-size: 11px; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.3rem; }
.card-value { font-size: 20px; font-weight: 700; }

.section-title { font-size: 13px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem; }

.config-row { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.config-row .form-group { flex: 1; min-width: 120px; }

.position-card { border: 1px solid var(--border); border-radius: var(--radius); padding: 0.75rem; margin-bottom: 0.5rem; }
.position-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.5rem; font-weight: 600; }
.position-row { display: flex; gap: 0.5rem; align-items: center; font-size: 13px; padding: 0.15rem 0; }

.log-entry { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0; border-bottom: 1px solid var(--border); font-size: 13px; }
.log-entry:last-child { border-bottom: none; }

.header-actions { display: flex; gap: 0.5rem; }
</style>
