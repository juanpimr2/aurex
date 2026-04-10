import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Backtest  from '../views/Backtest.vue'
import Settings  from '../views/Settings.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/',         component: Dashboard, name: 'dashboard' },
    { path: '/backtest', component: Backtest,  name: 'backtest' },
    { path: '/settings', component: Settings,  name: 'settings' },
  ],
})
