import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useTradingStore = defineStore('trading', () => {
  // ── State ────────────────────────────────────────────────────────────
  const botRunning   = ref(false)
  const balance      = ref(null)
  const positions    = ref([])
  const tradeLog     = ref([])
  const wsConnected  = ref(false)
  const livePrice    = ref(null)
  const lastError    = ref(null)
  const notifications= ref([])

  // ── Computed ─────────────────────────────────────────────────────────
  const totalPnL = computed(() =>
    positions.value.reduce((s, p) => s + (p.profit_loss || 0), 0)
  )

  // ── WebSocket ─────────────────────────────────────────────────────────
  let ws = null
  function connectWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return
    ws = new WebSocket(`ws://${location.hostname}:8000/ws`)

    ws.onopen = () => { wsConnected.value = true }
    ws.onclose = () => {
      wsConnected.value = false
      setTimeout(connectWS, 3000) // Reconectar
    }
    ws.onerror = () => { wsConnected.value = false }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'ping') return
      if (msg.type === 'price_update') {
        livePrice.value = msg.data
        if (msg.data.equity) {
          if (balance.value) balance.value.balance = msg.data.equity
        }
      }
      if (msg.type === 'trade_opened') {
        tradeLog.value.unshift(msg.data)
        addNotification(`Nueva operación: ${msg.data.direction} ${msg.data.epic}`, 'green')
      }
      if (msg.type === 'started') {
        botRunning.value = true
        addNotification('Bot iniciado', 'green')
      }
      if (msg.type === 'stopped') {
        botRunning.value = false
        addNotification('Bot detenido', 'yellow')
      }
      if (msg.type === 'error') {
        lastError.value = msg.data.message
        addNotification(`Error: ${msg.data.message}`, 'red')
      }
    }
  }

  // ── API calls ─────────────────────────────────────────────────────────
  async function fetchBalance() {
    try {
      const { data } = await axios.get('/api/balance')
      if (!data.error) balance.value = data
    } catch (e) { console.error('fetchBalance', e) }
  }

  async function fetchPositions() {
    try {
      const { data } = await axios.get('/api/positions')
      if (Array.isArray(data)) positions.value = data
    } catch (e) { console.error('fetchPositions', e) }
  }

  async function fetchStatus() {
    try {
      const { data } = await axios.get('/api/status')
      botRunning.value = data.running
      if (data.trader?.trade_log) tradeLog.value = data.trader.trade_log
    } catch (e) { console.error('fetchStatus', e) }
  }

  async function startBot(config) {
    try {
      const { data } = await axios.post('/api/start', config)
      if (data.ok) {
        botRunning.value = true
        addNotification(data.message, 'green')
      } else {
        addNotification(data.error || 'Error al iniciar', 'red')
      }
      return data
    } catch (e) {
      addNotification('Error al iniciar el bot', 'red')
      return { error: e.message }
    }
  }

  async function stopBot() {
    try {
      const { data } = await axios.post('/api/stop')
      if (data.ok) {
        botRunning.value = false
        addNotification(data.message, 'yellow')
      }
      return data
    } catch (e) {
      return { error: e.message }
    }
  }

  // ── Helpers ───────────────────────────────────────────────────────────
  function addNotification(message, type = 'blue') {
    const n = { id: Date.now(), message, type }
    notifications.value.unshift(n)
    if (notifications.value.length > 10) notifications.value.pop()
    setTimeout(() => {
      notifications.value = notifications.value.filter(x => x.id !== n.id)
    }, 5000)
  }

  return {
    botRunning, balance, positions, tradeLog, wsConnected, livePrice,
    lastError, notifications, totalPnL,
    connectWS, fetchBalance, fetchPositions, fetchStatus, startBot, stopBot,
    addNotification,
  }
})
