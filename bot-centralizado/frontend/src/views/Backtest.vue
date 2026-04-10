<template>
  <div>
    <div class="page-header">
      <div>
        <h1>Backtest</h1>
        <p class="text-muted">Verifica la estrategia contra datos históricos de Capital.com</p>
      </div>
    </div>

    <!-- Warning -->
    <div class="alert-info" style="margin-bottom:1rem">
      ⚠️ <strong>Nota sobre el 1499%:</strong> TradingView no incluye spread (~0.5 pts en GOLD),
      slippage ni financiación overnight. Este backtest simula condiciones reales de Capital.com.
    </div>

    <div class="grid-2">
      <!-- Config panel -->
      <div class="card">
        <div class="section-title">Configuración del Backtest</div>

        <div class="form-grid">
          <div class="form-group">
            <label>Activo</label>
            <select v-model="cfg.epic">
              <option value="GOLD">GOLD (XAU/USD)</option>
              <option value="US30">US30 (Dow Jones)</option>
              <option value="US500">US500 (S&P 500)</option>
              <option value="US100">US100 (NASDAQ)</option>
            </select>
          </div>
          <div class="form-group">
            <label>Timeframe</label>
            <select v-model="cfg.timeframe">
              <option value="MINUTE_15">15 min</option>
              <option value="MINUTE_30">30 min</option>
              <option value="HOUR">1H</option>
              <option value="HOUR_4">4H</option>
              <option value="DAY">1D</option>
            </select>
          </div>
          <div class="form-group">
            <label>Capital inicial (€)</label>
            <input v-model.number="cfg.initial_capital" type="number" />
          </div>
          <div class="form-group">
            <label>Riesgo por trade (%)</label>
            <input v-model.number="cfg.risk_pct" type="number" step="0.1" min="0.1" max="10" />
          </div>
          <div class="form-group">
            <label>Spread (puntos)</label>
            <input v-model.number="cfg.spread_points" type="number" step="0.1" />
          </div>
          <div class="form-group">
            <label>Máx. velas históricas</label>
            <input v-model.number="cfg.max_candles" type="number" step="100" min="100" max="1000" />
          </div>
        </div>

        <div class="section-title" style="margin-top:1.25rem">Parámetros de Estrategia</div>
        <div class="form-grid">
          <div class="form-group">
            <label>EMA Rápida</label>
            <input v-model.number="cfg.ema_fast" type="number" />
          </div>
          <div class="form-group">
            <label>EMA Lenta</label>
            <input v-model.number="cfg.ema_slow" type="number" />
          </div>
          <div class="form-group">
            <label>EMA Larga</label>
            <input v-model.number="cfg.ema_long" type="number" />
          </div>
          <div class="form-group">
            <label>Período RSI</label>
            <input v-model.number="cfg.rsi_period" type="number" />
          </div>
          <div class="form-group">
            <label>RSI Sobrecompra</label>
            <input v-model.number="cfg.rsi_overbought" type="number" />
          </div>
          <div class="form-group">
            <label>RSI Sobreventa</label>
            <input v-model.number="cfg.rsi_oversold" type="number" />
          </div>
          <div class="form-group">
            <label>ATR Período</label>
            <input v-model.number="cfg.atr_period" type="number" />
          </div>
          <div class="form-group">
            <label>ATR Mult SL</label>
            <input v-model.number="cfg.atr_sl_mult" type="number" step="0.1" />
          </div>
          <div class="form-group">
            <label>ATR Mult TP</label>
            <input v-model.number="cfg.atr_tp_mult" type="number" step="0.1" />
          </div>
        </div>

        <button class="btn btn-blue" style="margin-top:1.25rem; width:100%" @click="runBacktest" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>▶</span>
          {{ loading ? 'Ejecutando...' : 'Ejecutar Backtest' }}
        </button>
      </div>

      <!-- Results panel -->
      <div>
        <div v-if="error" class="card" style="margin-bottom:1rem; border-color:var(--red)">
          <span class="text-red">❌ {{ error }}</span>
        </div>

        <div v-if="results" class="card">
          <div class="section-title">Resultados</div>

          <!-- Veredicto -->
          <div class="verdict-box" :class="verdictClass">
            {{ results.stats.verdict }}
          </div>

          <!-- Stats grid -->
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-label">Capital Final</div>
              <div class="stat-value mono" :class="results.stats.final_equity >= cfg.initial_capital ? 'text-green' : 'text-red'">
                €{{ results.stats.final_equity?.toFixed(2) }}
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Retorno Total</div>
              <div class="stat-value mono" :class="results.stats.total_return_pct >= 0 ? 'text-green' : 'text-red'">
                {{ results.stats.total_return_pct >= 0 ? '+' : '' }}{{ results.stats.total_return_pct?.toFixed(1) }}%
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Win Rate</div>
              <div class="stat-value mono">{{ results.stats.win_rate_pct?.toFixed(1) }}%</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Profit Factor</div>
              <div class="stat-value mono">{{ results.stats.profit_factor }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Total Trades</div>
              <div class="stat-value mono">{{ results.stats.total_trades }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">W / L</div>
              <div class="stat-value mono">
                <span class="text-green">{{ results.stats.wins }}</span> /
                <span class="text-red">{{ results.stats.losses }}</span>
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Max Drawdown</div>
              <div class="stat-value mono text-red">{{ results.stats.max_drawdown_pct?.toFixed(1) }}%</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Expectativa</div>
              <div class="stat-value mono" :class="results.stats.expectancy_per_trade >= 0 ? 'text-green' : 'text-red'">
                €{{ results.stats.expectancy_per_trade?.toFixed(2) }}
              </div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Coste Spreads</div>
              <div class="stat-value mono text-red">-€{{ results.stats.total_spread_cost?.toFixed(2) }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Racha Gan. máx</div>
              <div class="stat-value mono text-green">{{ results.stats.max_win_streak }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Racha Pérd. máx</div>
              <div class="stat-value mono text-red">{{ results.stats.max_loss_streak }}</div>
            </div>
            <div class="stat-item">
              <div class="stat-label">Periodo</div>
              <div class="stat-value mono" style="font-size:11px">
                {{ results.total_candles }} velas
              </div>
            </div>
          </div>

          <div class="date-range">
            {{ results.date_range?.start?.slice(0,10) }} → {{ results.date_range?.end?.slice(0,10) }}
          </div>
        </div>
      </div>
    </div>

    <!-- Equity curve -->
    <div v-if="results?.equity_curve?.length" class="card" style="margin-top:1rem">
      <div class="section-title">Curva de Equity</div>
      <EquityChart :data="results.equity_curve" />
    </div>

    <!-- Trade log -->
    <div v-if="results?.trades?.length" class="card" style="margin-top:1rem">
      <div class="section-title">Últimas operaciones ({{ results.trades.length }})</div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Entrada</th>
              <th>Salida</th>
              <th>Dir.</th>
              <th>Entry</th>
              <th>Exit</th>
              <th>SL</th>
              <th>TP</th>
              <th>Resultado</th>
              <th>P&L €</th>
              <th>P&L %</th>
              <th>Equity</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="t in results.trades.slice().reverse().slice(0, 50)" :key="t.entry_time">
              <td>{{ t.entry_time?.slice(0,16) }}</td>
              <td>{{ t.exit_time?.slice(0,16) }}</td>
              <td>
                <span class="badge" :class="t.direction === 'LONG' ? 'badge-green' : 'badge-red'">
                  {{ t.direction }}
                </span>
              </td>
              <td>{{ t.entry_price?.toFixed(2) }}</td>
              <td>{{ t.exit_price?.toFixed(2) }}</td>
              <td class="text-red">{{ t.stop_loss?.toFixed(2) }}</td>
              <td class="text-green">{{ t.take_profit?.toFixed(2) }}</td>
              <td>
                <span class="badge" :class="t.result === 'WIN' ? 'badge-green' : 'badge-red'">
                  {{ t.result === 'WIN' ? '✓ WIN' : '✗ LOSS' }}
                </span>
              </td>
              <td :class="t.pnl_money >= 0 ? 'text-green' : 'text-red'">
                {{ t.pnl_money >= 0 ? '+' : '' }}€{{ t.pnl_money?.toFixed(2) }}
              </td>
              <td :class="t.pnl_pct >= 0 ? 'text-green' : 'text-red'">
                {{ t.pnl_pct >= 0 ? '+' : '' }}{{ t.pnl_pct?.toFixed(2) }}%
              </td>
              <td class="mono">€{{ t.equity_after?.toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'
import EquityChart from '../components/EquityChart.vue'

const loading = ref(false)
const error = ref(null)
const results = ref(null)

const cfg = ref({
  epic: 'GOLD',
  timeframe: 'DAY',
  initial_capital: 300,
  risk_pct: 1.5,
  spread_points: 0.5,
  max_candles: 500,
  ema_fast: 8,
  ema_slow: 21,
  ema_long: 50,
  rsi_period: 14,
  rsi_overbought: 65,
  rsi_oversold: 35,
  atr_period: 14,
  atr_sl_mult: 1.0,
  atr_tp_mult: 2.5,
})

const verdictClass = computed(() => {
  const v = results.value?.stats?.verdict || ''
  if (v.includes('RENTABLE')) return 'verdict-green'
  if (v.includes('MARGINAL')) return 'verdict-yellow'
  return 'verdict-red'
})

async function runBacktest() {
  loading.value = true
  error.value = null
  results.value = null
  try {
    const { data } = await axios.post('/api/backtest', cfg.value)
    if (data.error) {
      error.value = data.error
    } else {
      results.value = data
    }
  } catch (e) {
    error.value = e.message || 'Error de conexión'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page-header { margin-bottom: 1.5rem; }
.page-header h1 { font-size: 20px; font-weight: 700; }

.alert-info {
  background: rgba(88,166,255,0.1);
  border: 1px solid rgba(88,166,255,0.3);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  font-size: 13px;
  color: var(--text);
}

.section-title { font-size: 12px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem; }

.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 0.75rem; }

.verdict-box {
  padding: 0.75rem 1rem;
  border-radius: var(--radius);
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 1rem;
  border: 1px solid;
}
.verdict-green  { background: rgba(63,185,80,0.1);  border-color: var(--green); color: var(--green); }
.verdict-yellow { background: rgba(210,153,34,0.1); border-color: var(--yellow); color: var(--yellow); }
.verdict-red    { background: rgba(248,81,73,0.1);  border-color: var(--red);   color: var(--red); }

.stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 0.75rem; }
.stat-item { background: var(--bg3); border-radius: var(--radius); padding: 0.6rem 0.75rem; }
.stat-label { font-size: 11px; color: var(--text2); margin-bottom: 0.25rem; }
.stat-value { font-size: 16px; font-weight: 700; }

.date-range { margin-top: 0.75rem; font-size: 11px; color: var(--text2); font-family: var(--mono); }
</style>
