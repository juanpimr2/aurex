import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import axios from 'axios'

export const useTradingStore = defineStore('trading', () => {
  const balance = ref(null)
  const positions = ref([])
  const tradeLog = ref([])
  const wsConnected = ref(false)
  const livePrice = ref(null)
  const lastError = ref(null)
  const notifications = ref([])
  const lastRefresh = ref(null)
  const runtimeStatus = ref(null)

  const totalPnL = computed(() =>
    positions.value.reduce((sum, position) => sum + (position.profit_loss || 0), 0)
  )

  const councilVerdict = computed(() => {
    if (runtimeStatus.value?.verdict) return runtimeStatus.value.verdict
    if (positions.value.length > 0) return 'REVIEW_REQUIRED'
    return 'NO_GO_FOR_REAL_TRADING'
  })

  const runtimeGates = computed(() => {
    const gates = runtimeStatus.value?.runtime_gates || []
    return gates.map((gate) => ({
      name: gate.name.replaceAll('_', ' '),
      status: gate.allowed ? 'running' : 'blocked',
      detail: gate.reason,
    }))
  })

  const runtimeEvents = computed(() => {
    const contractEvents = runtimeStatus.value?.events?.map((event) => ({
      label: event.level === 'warning' ? 'Runtime warning' : 'Runtime event',
      status: event.level === 'warning' ? 'warning' : 'running',
      detail: event.message,
    })) || []
    const events = [
      ...contractEvents,
      {
        label: 'Council live watch',
        status: 'warning',
        detail: 'Not running by default; dashboard remains read-only',
      },
      {
        label: 'Broker mutations',
        status: 'blocked',
        detail: 'REAL requires explicit double opt-in',
      },
      {
        label: 'Legacy runtime',
        status: 'blocked',
        detail: 'Disabled unless isolated lab opt-in is set',
      },
    ]
    if (lastError.value) {
      events.unshift({
        label: 'API status',
        status: 'warning',
        detail: lastError.value,
      })
    }
    return events
  })

  let ws = null

  function connectWS() {
    if (ws && ws.readyState === WebSocket.OPEN) return
    ws = new WebSocket(`ws://${location.hostname}:8000/ws`)

    ws.onopen = () => { wsConnected.value = true }
    ws.onclose = () => {
      wsConnected.value = false
      setTimeout(connectWS, 3000)
    }
    ws.onerror = () => { wsConnected.value = false }
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'ping') return
      if (msg.type === 'price_update') {
        livePrice.value = msg.data
        if (msg.data.equity && balance.value) {
          balance.value.balance = msg.data.equity
        }
      }
      if (msg.type === 'error') {
        lastError.value = msg.data.message
        addNotification(`API error: ${msg.data.message}`, 'red')
      }
    }
  }

  function normalizePosition(position) {
    return {
      ...position,
      direction: position.direction || position.dir,
      entry_price: position.entry_price ?? position.entry,
      stop_loss: position.stop_loss ?? position.sl,
      take_profit: position.take_profit ?? position.tp,
      profit_loss: position.profit_loss ?? position.pnl ?? 0,
    }
  }

  async function fetchRuntimeStatus() {
    try {
      const { data } = await axios.get('/api/runtime/status')
      runtimeStatus.value = data
      if (data.account?.balance) balance.value = data.account.balance
      if (Array.isArray(data.account?.positions)) {
        positions.value = data.account.positions.map(normalizePosition)
      }
      if (data.errors?.length) lastError.value = data.errors.join('; ')
      return true
    } catch (error) {
      lastError.value = error.message
      return false
    }
  }

  async function fetchBalance() {
    try {
      const { data } = await axios.get('/api/balance')
      if (!data.error) balance.value = data
    } catch (error) {
      lastError.value = error.message
    }
  }

  async function fetchPositions() {
    try {
      const { data } = await axios.get('/api/positions')
      if (Array.isArray(data)) positions.value = data
    } catch (error) {
      lastError.value = error.message
    }
  }

  async function fetchStatus() {
    try {
      const { data } = await axios.get('/api/status')
      if (data.trader?.trade_log) tradeLog.value = data.trader.trade_log
    } catch (error) {
      lastError.value = error.message
    }
  }

  async function refreshReadOnly() {
    const runtimeOk = await fetchRuntimeStatus()
    if (!runtimeOk) {
      await Promise.all([fetchBalance(), fetchPositions(), fetchStatus()])
    }
    lastRefresh.value = new Date().toISOString()
  }

  function addNotification(message, type = 'blue') {
    const n = { id: Date.now(), message, type }
    notifications.value.unshift(n)
    if (notifications.value.length > 10) notifications.value.pop()
    setTimeout(() => {
      notifications.value = notifications.value.filter(item => item.id !== n.id)
    }, 5000)
  }

  return {
    balance,
    positions,
    tradeLog,
    wsConnected,
    livePrice,
    lastError,
    notifications,
    lastRefresh,
    runtimeStatus,
    totalPnL,
    councilVerdict,
    runtimeGates,
    runtimeEvents,
    connectWS,
    fetchRuntimeStatus,
    fetchBalance,
    fetchPositions,
    fetchStatus,
    refreshReadOnly,
    addNotification,
  }
})
