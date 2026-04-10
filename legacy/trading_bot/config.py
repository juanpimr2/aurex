"""
Configuración del Auto-Trader SMC
=================================
⚠️ IMPORTANTE: Cambia estas credenciales después de compartirlas
"""

# CREDENCIALES API - ¡CAMBIAR ESTAS!
API_KEY = "MBnb7mcX81ERKXwM"
PASSWORD = "Kamikaze.58"
EMAIL = "juanpablomore58@gmail.com"
BASE_URL = "https://api-capital.backend-capital.com/api/v1"

# Para DEMO usa:
# BASE_URL = "https://demo-api-capital.backend-capital.com/api/v1"

# ACTIVOS A MONITOREAR
ASSETS = [
    "GOLD",              # Oro (XAU/USD)
    "US30",              # Dow Jones
]

# CONFIGURACIÓN DE RIESGO
RISK_PER_TRADE_PCT = 2.0    # % del balance por operación
MAX_POSITIONS = 2           # Máximo de posiciones simultáneas
MIN_CONFIDENCE = 60         # Confianza mínima para ejecutar (0-100)

# CONFIGURACIÓN TÉCNICA
CHECK_INTERVAL = 30         # Segundos entre cada revisión
CANDLES_HISTORY = 200       # Velas históricas a analizar

# SMC SETTINGS
OB_LOOKBACK = 20            # Velas para detectar Order Blocks
FVG_MIN_SIZE = 0.002        # Tamaño mínimo de FVG (%)
