"""
Configuración del Generador de Informes para IA
===============================================
"""

# CREDENCIALES API
API_KEY = "MBnb7mcX81ERKXwM"
PASSWORD = "Kamikaze.58"
EMAIL = "juanpablomore58@gmail.com"
BASE_URL = "https://api-capital.backend-capital.com/api/v1"

# ACTIVOS A ANALIZAR
# Nota: Verificar los epics exactos disponibles en Capital.com
ASSETS = [
    # Materias primas
    "GOLD",              # Oro (XAU/USD)
    "OIL_CRUDE",         # Petróleo Crudo (WTI)
    # Índices USA
    "US30",              # Dow Jones Industrial Average
    "US500",             # S&P 500  
    "US100",             # NASDAQ 100
]

# Para acciones individuales, verificar disponibilidad:
# NVIDIA puede ser: "NVDA", "NVIDIA", "NVDA.OQ"
# TESLA puede ser: "TSLA", "TESLA", "TSLA.OQ"

# CONFIGURACIÓN TÉCNICA
TIMEFRAME = "HOUR"         # Timeframe principal
CANDLES_HISTORY = 200      # Velas históricas a obtener

# SMC SETTINGS  
OB_LOOKBACK = 20          # Velas hacia atrás para Order Blocks
FVG_MIN_SIZE = 0.002      # Tamaño mínimo de Fair Value Gap (%)
MIN_CONFLUENCES = 3       # Mínimo de señales SMC

# NOTA: El generador de informes NO gestiona riesgo
# Solo genera datos para análisis por IA
