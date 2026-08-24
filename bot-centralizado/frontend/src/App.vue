<template>
  <div id="layout">
    <nav class="sidebar">
      <div class="logo">
        <span class="logo-mark">AX</span>
        <div>
          <span class="logo-text">Aurex</span>
          <span class="logo-subtitle">Operations</span>
        </div>
      </div>

      <div class="nav-links">
        <router-link to="/" class="nav-link" active-class="active">Dashboard</router-link>
        <router-link to="/backtest" class="nav-link" active-class="active">Backtest</router-link>
        <router-link to="/settings" class="nav-link" active-class="active">Settings</router-link>
      </div>

      <div class="sidebar-footer">
        <div class="status-row">
          <span class="dot" :class="store.wsConnected ? 'dot-green' : 'dot-gray'"></span>
          <span>{{ store.wsConnected ? 'API connected' : 'API offline' }}</span>
        </div>
        <div class="status-row">
          <span class="dot dot-yellow"></span>
          <span>Read-only mode</span>
        </div>
      </div>
    </nav>

    <main class="main">
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
  store.refreshReadOnly()
  setInterval(store.refreshReadOnly, 30_000)
})
</script>

<style>
#layout {
  display: flex;
  min-height: 100vh;
}

.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--surface);
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
  gap: 0.75rem;
  padding: 0.5rem 0 1.25rem;
  border-bottom: 1px solid var(--border);
  margin-bottom: 1rem;
}

.logo-mark {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: var(--accent);
  color: #07110d;
  font-weight: 800;
  font-size: 13px;
}

.logo-text,
.logo-subtitle {
  display: block;
}

.logo-text {
  font-weight: 700;
  font-size: 15px;
}

.logo-subtitle {
  color: var(--muted);
  font-size: 12px;
}

.nav-links {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.nav-link {
  padding: 0.55rem 0.75rem;
  border-radius: var(--radius);
  color: var(--muted);
  font-size: 14px;
  transition: all 0.15s;
}

.nav-link:hover {
  background: var(--surface-strong);
  color: var(--text);
}

.nav-link.active {
  background: rgba(72, 187, 120, 0.12);
  color: var(--accent);
}

.sidebar-footer {
  margin-top: auto;
  padding-top: 1rem;
  border-top: 1px solid var(--border);
  display: grid;
  gap: 0.6rem;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--muted);
  font-size: 12px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--muted);
}

.dot-green { background: var(--accent); }
.dot-yellow { background: var(--warning); }
.dot-gray { background: var(--muted); }

.main {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  position: relative;
}

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

.notif-green { background: rgba(72,187,120,0.15); border-color: var(--accent); color: var(--accent); }
.notif-red { background: rgba(248,81,73,0.15); border-color: var(--danger); color: var(--danger); }
.notif-yellow { background: rgba(245,158,11,0.15); border-color: var(--warning); color: var(--warning); }
.notif-blue { background: rgba(56,189,248,0.15); border-color: var(--info); color: var(--info); }

.notif-enter-active,
.notif-leave-active {
  transition: all 0.3s;
}

.notif-enter-from,
.notif-leave-to {
  opacity: 0;
  transform: translateX(20px);
}

@media (max-width: 760px) {
  #layout {
    display: block;
  }

  .sidebar {
    width: 100%;
    min-width: 0;
    height: auto;
    position: static;
  }

  .nav-links {
    flex-direction: row;
    overflow-x: auto;
  }
}
</style>
