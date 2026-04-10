# 🤖 Trading Report Generator for AI Analysis

Generador de informes exhaustivos de mercados para ser analizados por Claude/IA.

## 📋 Concepto

En lugar de que el bot tome decisiones de trading, este sistema:

1. **Extrae todos los datos** relevantes de cada activo
2. **Genera informes estructurados** (JSON + Markdown)
3. **Tú pasas el informe a Claude** para análisis profundo
4. **Claude genera señales** con Entry, SL, TP1, TP2

## 🔧 Instalación

```bash
# Clonar o copiar los archivos
pip install pandas numpy requests

# Configurar credenciales en config.py
```

## ⚙️ Configuración

Edita `config.py`:

```python
# Tus credenciales de Capital.com
API_KEY = "tu_api_key"
PASSWORD = "tu_password"
EMAIL = "tu_email"

# Activos a analizar
ASSETS = [
    "GOLD",      # Oro
    "US30",      # Dow Jones
    "US500",     # S&P 500
    "US100",     # NASDAQ
    # Añade más según necesites
]
```

### Encontrar EPICs de acciones

Para acciones como NVIDIA o TESLA, los nombres pueden variar:
- NVIDIA: `"NVDA"`, `"NVIDIA"`, `"NVDA.OQ"`
- TESLA: `"TSLA"`, `"TESLA"`, `"TSLA.OQ"`

Puedes verificar en la plataforma de Capital.com o usar la API:
```python
# Script para buscar EPICs
import requests
session = requests.Session()
# ... (autenticar)
r = session.get(f"{BASE_URL}/markets?searchTerm=NVIDIA")
print(r.json())
```

## 🚀 Uso

```bash
python report_generator.py
```

Esto generará:
- `reports/YYYY-MM-DD_HHhMM_analysis.json` - Datos completos
- `reports/YYYY-MM-DD_HHhMM_analysis.md` - Versión legible

## 📊 Qué incluye cada informe

Para cada activo:

### Price Action
- Precio actual, cambios diarios/semanales
- Posición en rangos
- Tendencia (EMA 20/50)

### Indicadores Técnicos (H1, H4, D1)
- RSI, MACD, Bollinger Bands
- EMAs (9, 21, 50, 200)
- SMAs (20, 50)
- ATR, Pivot Points

### Análisis SMC
- Order Blocks (alcistas/bajistas)
- Fair Value Gaps
- Break of Structure
- Liquidity Sweeps
- Zonas Premium/Discount

### Niveles Clave
- Soportes y resistencias
- Pivot points
- Fortaleza de cada nivel

### Datos Crudos
- Últimas 20 velas H1
- Últimas 10 velas H4
- Últimas 5 velas D1

## 🎯 Uso con Claude

1. Ejecuta el generador
2. Copia el contenido del `.md` o `.json`
3. Pégalo en un chat con Claude
4. Pide análisis específico:

```
Analiza este informe del oro. Busca oportunidades de:
- Scalping (entrada rápida, 10-20 pips)
- Intraday (mantener 1-4 horas)
- Swing (mantener 1-3 días)

Dame señales con Entry, SL, TP1, TP2.
Explica tu razonamiento basándote en SMC.
```

## 📁 Estructura del Proyecto

```
trading-reports/
├── config.py              # Configuración y credenciales
├── indicators_smc.py      # Indicadores Smart Money Concepts
├── report_generator.py    # Generador principal
├── reports/               # Informes generados
│   ├── YYYY-MM-DD_analysis.json
│   └── YYYY-MM-DD_analysis.md
└── README.md
```

## ⚠️ Notas Importantes

- **El bot NO opera** - Solo genera informes
- **Tú gestionas el riesgo** - Capital y posiciones
- **Claude analiza** - Pero tú decides
- **Verifica siempre** - Los mercados son impredecibles

## 🔄 Automatización (Opcional)

Puedes programar ejecuciones con cron:

```bash
# Ejecutar a las 9:00, 15:30 y 21:00
0 9,15,21 * * 1-5 cd /ruta/trading-reports && python report_generator.py
```

O integrar con Telegram para recibir notificaciones.

---

**Autor:** Juanpi  
**Versión:** 2.0  
**Última actualización:** 2026-01-11
