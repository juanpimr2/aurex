# 🤖 Bot Millonario v2.0

Sistema de trading algorítmico centralizado con dashboard Vue 3.

## Estrategia

**EMA Triple Cross + RSI + Bollinger + ATR** (del Pine Script XAUUSD)

| Parámetro | Valor |
|-----------|-------|
| EMA Rápida/Lenta/Larga | 6 / 18 / 30 |
| RSI | 14 (rango 30–70) |
| Bollinger | 20, desv 2.0 |
| ATR SL | 0.8x |
| ATR TP | 2.0x (R:R = 2.5) |
| Riesgo | 1.5% equity/trade |

## Estructura

```
bot-centralizado/
├── backend/
│   ├── main.py          # API FastAPI (REST + WebSocket)
│   ├── capital_client.py# Cliente Capital.com
│   ├── strategy.py      # Estrategia EMA/RSI/ATR
│   ├── backtester.py    # Motor de backtesting
│   ├── trader.py        # Trading en vivo
│   └── .env             # Credenciales (NO subir a GitHub)
└── frontend/
    └── src/
        ├── views/
        │   ├── Dashboard.vue   # Estado en tiempo real
        │   ├── Backtest.vue    # Backtest con gráfico
        │   └── Settings.vue    # Configuración
        └── stores/trading.js   # Estado global (Pinia)
```

## Instalación

### Backend
```bash
cd backend
pip install -r requirements.txt
# Editar .env con tus credenciales
python main.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Luego abre http://localhost:5173

## Uso

1. **Backtest primero** → Ir a `/backtest`, configurar y ejecutar
2. **Revisar resultados** → Win rate, Profit Factor, Max Drawdown
3. **Demo antes que Real** → Asegúrate de que `CAPITAL_MODE=DEMO` en `.env`
4. **Iniciar bot** → Dashboard → configurar parámetros → "Iniciar Bot"

## ⚠️ Advertencias

- Empieza siempre en DEMO
- Con €300 de capital, las posiciones serán pequeñas (correcto)
- El bot NO tiene cap artificial de tamaño: el riesgo % lo gestiona todo
- Los resultados pasados no garantizan resultados futuros
