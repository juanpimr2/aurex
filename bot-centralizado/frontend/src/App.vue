<template>
  <div id="layout">
    <!-- Sidebar -->
    <nav class="sidebar">
      <div class="logo">
        <span class="logo-icon">🤖</span>
        <span class="logo-text">BotMillonario</span>
      </div>

      <div class="nav-links">
        <router-link to="/" class="nav-link" active-class="active">
          <span>📊</span> Dashboard
        </router-link>
        <router-link to="/backtest" class="nav-link" active-class="active">
          <span>🔬</span> Backtest
        </router-link>
        <router-link to="/settings" class="nav-link" active-class="active">
          <span>⚙️</span> Configuración
        </router-link>
      </div>

      <!-- Status indicators -->
      <div class="sidebar-footer">
        <div class="status-row">
          <span class="dot" :class="store.wsConnected ? 'dot-green' : 'dot-red'"></span>
          <span class="text-muted" style="font-size:12px">
            {{ store.wsConnected ? 'Conectado' : 'Sin conexión' }}
          </span>
        </div>
        <div class="status-row" style="margin-top:0.5rem">
          <span class="dot" :class="store.botRunning ? 'dot-green blink' : 'dot-gray'"></span>
          <span class="text-muted" style="font-size:12px">
            Bot {{ store.botRunning ? 'activo' : 'inactivo' }}
          </span>
        </div>
      </div>
    </nav>

    <!-- Main content -->
    <main class="main">
      <!-- Notifications -->
      <div class="notifications">
        <transition-group name="notif">
          <div
            v-for="n in store.notifications"
            :key="n.id"
            class="notif"
            :class="`notif-${n.type}`"
          >{{ n.message }}</div>
        </transition-group>
      </div>

      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useTradingStore } from './stores/trading.js'

const store = useTradingStore()
onMounted(() => {
  store.connectWS()
  store.fetchBalance()
  store.fetchStatus()
  // Refresh cada 30 segundos
  setInterval(() => { store.fetchBalance(); store.fetchPositions() }, 30_000)
})
</script>

<style>
#layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar */
.sidebar {
  width: 200px;
  min-width: 200px;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 1rem;
  position: sticky;
  top: 0;
  height: 100vh;
}

.logo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0 1.5rem;
  font-weight: 700;
  font-size: 15px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}

.logo-icon { font-size: 1.4rem; }

.nav-links { display: flex; flex-direction: column; gap: 0.25rem; flex: 1; }

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.5rem 0.75rem;
  border-radius: var(--radius);
  color: var(--text2);
  font-size: 14px;
  transition: all 0.15s;
}
.nav-link:hover { background: var(--bg3); color: var(--text); }
.nav-link.active { background: rgba(88,166,255,0.15); color: var(--blue); }

.sidebar-footer { margin-top: auto; padding-top: 1rem; border-top: 1px solid var(--border); }

.status-row { display: flex; align-items: center; gap: 0.5rem; }

.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--text2);
}
.dot-green { background: var(--green); }
.dot-red   { background: var(--red); }
.dot-gray  { background: var(--text2); }
.blink { animation: blink 1.5s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* Main */
.main {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  position: relative;
}

/* Notifications */
.notifications {
  position: fixed;
  top: 1rem;
  right: 1rem;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 280px;
}

.notif {
  padding: 0.6rem 1rem;
  border-radius: var(--radius);
  font-size: 13px;
  font-weight: 500;
  border: 1px solid;
}
.notif-green  { background: rgba(63,185,80,0.15);  border-color: var(--green); color: var(--green); }
.notif-red    { background: rgba(248,81,73,0.15);   border-color: var(--red);   color: var(--red); }
.notif-yellow { background: rgba(210,153,34,0.15);  border-color: var(--yellow);color: var(--yellow); }
.notif-blue   { background: rgba(88,166,255,0.15);  border-color: var(--blue);  color: var(--blue); }

/* Transition */
.notif-enter-active, .notif-leave-active { transition: all 0.3s; }
.notif-enter-from { opacity: 0; transform: translateX(20px); }
.notif-leave-to   { opacity: 0; transform: translateX(20px); }
</style>
