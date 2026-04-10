# 🤖 Auto-Trader SMC v1.0

Sistema de trading automático basado en Smart Money Concepts para Capital.com.

## 🎯 Qué hace

1. **Analiza mercados** usando SMC (Order Blocks, FVGs, Premium/Discount)
2. **Detecta zonas de entrada** automáticamente
3. **Monitorea precios** en tiempo real
4. **Ejecuta trades** cuando el precio entra en zona + confirmaciones
5. **Gestiona riesgo** (SL/TP automáticos basados en ATR)

## 📦 Instalación

```bash
pip install pandas numpy requests websockets
```

## ⚙️ Configuración

Edita `config.py`:

```python
# Tus credenciales
API_KEY = "tu_api_key"
PASSWORD = "tu_password"
EMAIL = "tu_email"

# Activos a monitorear
ASSETS = ["GOLD", "US30"]

# Gestión de riesgo
RISK_PER_TRADE_PCT = 2.0    # % del balance por trade
MAX_POSITIONS = 2            # Máximo posiciones abiertas
MIN_CONFIDENCE = 60          # Confianza mínima (0-100)
```

## 🚀 Uso

```bash
python auto_trader.py
```

### Añadir zonas manuales

En el código, antes de `trader.start()`:

```python
# Zona de demanda para LONG
trader.add_manual_zone('GOLD', 4570, 4580, 'LONG')

# Zona de oferta para SHORT
trader.add_manual_zone('GOLD', 4620, 4640, 'SHORT')
```

## 📊 Señales y Confirmaciones

El bot genera señales cuando:

1. **Precio entra en zona** (FVG, Order Block, o manual)
2. **Confirmaciones adicionales**:
   - RSI en sobreventa (<40) para LONG
   - RSI en sobrecompra (>60) para SHORT
   - Precio en zona Discount para LONG
   - Precio en zona Premium para SHORT

**Confianza mínima**: 60% (configurable)

## 🛡️ Gestión de Riesgo

- **Stop Loss**: ATR × 1.5 desde la zona
- **Take Profit 1**: ATR × 2 desde entrada
- **Take Profit 2**: ATR × 3 desde entrada
- **Tamaño de posición**: Basado en % de riesgo del balance

## 📁 Estructura

```
trading_bot/
├── auto_trader.py    # Bot principal
├── config.py         # Configuración
└── README.md         # Este archivo
```

## ⚠️ Advertencias

- **Esto es trading real con dinero real**
- Usa primero con cuenta DEMO
- El bot NO garantiza ganancias
- Los mercados son impredecibles
- **CAMBIA TUS CREDENCIALES** si las compartiste

## 🔧 Personalización

### Cambiar a cuenta DEMO

En `config.py`:
```python
BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"
```

### Aumentar/reducir frecuencia de revisión

```python
CHECK_INTERVAL = 15  # Revisar cada 15 segundos
```

### Cambiar criterios de confianza

En `auto_trader.py`, función `_generate_signal()`:
- Modifica los valores de confirmaciones
- Ajusta el cálculo de confianza

---

**Autor:** Juanpi + Claude  
**Versión:** 1.0  
**Última actualización:** 2026-01-15
