<template>
  <div class="chart-wrapper">
    <canvas ref="canvas"></canvas>
    <div v-if="!data.length" class="chart-empty">
      <span class="text-muted">Sin datos aún</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, onUnmounted } from 'vue'
import { Chart, LineController, LineElement, PointElement, LinearScale,
         TimeScale, Filler, Tooltip, CategoryScale } from 'chart.js'

Chart.register(LineController, LineElement, PointElement, LinearScale,
               Filler, Tooltip, CategoryScale)

const props = defineProps({
  data: { type: Array, default: () => [] },   // [{ time, equity }]
  color: { type: String, default: '#58a6ff' },
})

const canvas = ref(null)
let chart = null

function buildChart() {
  if (!canvas.value || !props.data.length) return
  if (chart) chart.destroy()

  const labels = props.data.map(d => {
    const dt = new Date(d.time)
    return dt.toLocaleDateString('es', { month: 'short', day: 'numeric' })
  })
  const values = props.data.map(d => d.equity)
  const isProfit = values[values.length - 1] >= values[0]
  const lineColor = isProfit ? '#3fb950' : '#f85149'

  chart = new Chart(canvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data: values,
        borderColor: lineColor,
        backgroundColor: lineColor + '22',
        borderWidth: 2,
        fill: true,
        pointRadius: 0,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: {
          label: ctx => ` €${ctx.parsed.y.toFixed(2)}`,
        },
      }},
      scales: {
        x: {
          grid: { color: '#30363d' },
          ticks: { color: '#8b949e', maxTicksLimit: 8, font: { family: 'JetBrains Mono', size: 11 } },
        },
        y: {
          grid: { color: '#30363d' },
          ticks: { color: '#8b949e', font: { family: 'JetBrains Mono', size: 11 },
                   callback: v => `€${v.toFixed(0)}` },
        },
      },
    },
  })
}

onMounted(buildChart)
watch(() => props.data, buildChart, { deep: true })
onUnmounted(() => chart?.destroy())
</script>

<style scoped>
.chart-wrapper {
  position: relative;
  width: 100%;
  height: 220px;
}
.chart-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
