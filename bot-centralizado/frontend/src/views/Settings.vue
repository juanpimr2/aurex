<template>
  <div>
    <h1 style="font-size:20px;font-weight:700;margin-bottom:0.5rem">Configuración</h1>
    <p class="text-muted" style="margin-bottom:1.5rem">Gestión de credenciales y parámetros globales</p>

    <!-- Credenciales -->
    <div class="card" style="margin-bottom:1rem">
      <div class="section-title">Credenciales Capital.com</div>
      <div class="alert-warn" style="margin-bottom:1rem">
        🔒 Las credenciales se almacenan en el archivo <code>.env</code> del backend.
        <strong>NUNCA las incluyas en el código ni en GitHub.</strong>
      </div>
      <div class="form-grid">
        <div class="form-group">
          <label>API Key</label>
          <input v-model="creds.api_key" type="password" placeholder="MBnb7mcX81ERKXwM..." />
        </div>
        <div class="form-group">
          <label>Email</label>
          <input v-model="creds.email" type="email" placeholder="tu@email.com" />
        </div>
        <div class="form-group">
          <label>Password</label>
          <input v-model="creds.password" type="password" placeholder="••••••••" />
        </div>
        <div class="form-group">
          <label>Modo</label>
          <select v-model="creds.mode">
            <option value="DEMO">DEMO (recomendado para pruebas)</option>
            <option value="REAL">REAL (dinero real)</option>
          </select>
        </div>
      </div>
      <div style="margin-top:1rem">
        <p class="text-muted" style="font-size:12px">
          Para cambiar credenciales, edita el archivo
          <code>bot-centralizado/backend/.env</code> directamente:
        </p>
        <pre class="code-block">CAPITAL_API_KEY=tu_key
CAPITAL_PASSWORD=tu_password
CAPITAL_EMAIL=tu@email.com
CAPITAL_MODE=DEMO</pre>
      </div>
    </div>

    <!-- Test de conexión -->
    <div class="card" style="margin-bottom:1rem">
      <div class="section-title">Test de Conexión</div>
      <button class="btn btn-blue" @click="testConnection" :disabled="testing">
        <span v-if="testing" class="spinner"></span>
        🔌 Probar conexión con Capital.com
      </button>
      <div v-if="testResult" class="test-result" :class="testResult.ok ? 'test-ok' : 'test-fail'" style="margin-top:0.75rem">
        <span v-if="testResult.ok">
          ✅ Conectado. Balance: €{{ testResult.balance?.toFixed(2) }}
          | Disponible: €{{ testResult.available?.toFixed(2) }}
        </span>
        <span v-else>❌ Error: {{ testResult.error }}</span>
      </div>
    </div>

    <!-- Info sobre la estrategia -->
    <div class="card">
      <div class="section-title">Sobre la Estrategia</div>
      <div class="strategy-info">
        <p>La estrategia implementada es la del Pine Script <em>"XAUUSD Strategy - Control de Drawdown"</em>:</p>
        <ul>
          <li><strong>Triple EMA</strong> (6/18/30): Filtro de tendencia</li>
          <li><strong>RSI 14</strong> (30-70): Solo entrar cuando NO está en extremos</li>
          <li><strong>Bollinger Bands</strong> (20, 2): El precio debe estar dentro de las bandas</li>
          <li><strong>Volumen</strong>: Por encima de la media de 50 periodos</li>
          <li><strong>ATR SL</strong>: 0.8x ATR (sin cap artificial — el tamaño se ajusta al riesgo)</li>
          <li><strong>ATR TP</strong>: 2.0x ATR (R:R de 2.5)</li>
          <li><strong>Riesgo</strong>: 1.5% del equity por operación con compounding</li>
        </ul>
        <p style="margin-top:0.75rem" class="text-muted">
          El 1499% en TradingView se debe principalmente a: compounding agresivo en la tendencia alcista
          del oro 2020-2025 + no incluye spreads reales. Nuestro backtest simula condiciones reales.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'

const testing = ref(false)
const testResult = ref(null)

const creds = ref({
  api_key: '',
  email: '',
  password: '',
  mode: 'DEMO',
})

async function testConnection() {
  testing.value = true
  testResult.value = null
  try {
    const { data } = await axios.get('/api/balance')
    if (data.error) {
      testResult.value = { ok: false, error: data.error }
    } else {
      testResult.value = { ok: true, ...data }
    }
  } catch (e) {
    testResult.value = { ok: false, error: e.message }
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.section-title { font-size: 12px; font-weight: 600; color: var(--text2); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.75rem; }

.alert-warn {
  background: rgba(210,153,34,0.1);
  border: 1px solid rgba(210,153,34,0.3);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  font-size: 13px;
}

.form-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; }

.code-block {
  background: var(--bg3);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  margin-top: 0.5rem;
  font-family: var(--mono);
  font-size: 12px;
  color: var(--text);
  white-space: pre;
  overflow-x: auto;
}

code {
  background: var(--bg3);
  padding: 0.1rem 0.4rem;
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 12px;
}

.test-result { padding: 0.6rem 1rem; border-radius: var(--radius); font-size: 13px; border: 1px solid; }
.test-ok   { background: rgba(63,185,80,0.1);  border-color: var(--green); color: var(--green); }
.test-fail { background: rgba(248,81,73,0.1);  border-color: var(--red);   color: var(--red); }

.strategy-info { font-size: 13px; color: var(--text); line-height: 1.7; }
.strategy-info ul { margin: 0.5rem 0 0.5rem 1.25rem; }
.strategy-info li { margin-bottom: 0.25rem; }
</style>
