# -*- coding: utf-8 -*-
"""
Aurex — Macro Context (capa de noticias / eventos de alto impacto)
==================================================================
REGLA DE ORO: las noticias y eventos macro son SOLO CONTEXTO.
NUNCA disparan una operación. Sirven para:
  - Anticipar volatilidad (ej. FOMC, CPI, NFP mueven GOLD con fuerza)
  - Interpretar movimientos bruscos ya ocurridos
  - Subir el listón de cautela técnica alrededor del evento

Dos capas:
  1) Calendario determinista (este módulo): eventos con fecha fija/calculable
     (FOMC con fecha oficial publicada por la Fed + NFP = primer viernes de mes).
     Cero llamadas de red — fiable y rápido. Se integra en los monitores.
  2) Noticias en vivo (geopolítica, acciones de gobierno, Fed speakers): las
     revisa Claude vía WebSearch sobre FUENTES OFICIALES durante el reporte
     diario y el briefing semanal. Ver MACRO_WATCHLIST abajo.

Fuente FOMC 2026: federalreserve.gov/monetarypolicy/fomccalendars.htm
"""
from datetime import datetime, timezone, timedelta

# ── Capa 1: Calendario determinista ─────────────────────────────────────────

# FOMC 2026 — día de la DECISIÓN (segundo día de cada reunión).
# El comunicado sale ~18:00 UTC y la rueda de prensa ~18:30 UTC.
# Fuente oficial: Federal Reserve FOMC calendar.
FOMC_2026 = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
]
FOMC_STATEMENT_HOUR_UTC = 18.0   # comunicado ~14:00 ET = 18:00 UTC (verano)

# Hora típica de datos USA de alto impacto (8:30 ET):
#   verano (EDT) = 12:30 UTC | invierno (EST) = 13:30 UTC. Usamos 12:30 aprox.
US_DATA_HOUR_UTC = 12.5

# Ventanas de cautela (horas alrededor del evento)
WINDOW_HIGH_H   = 6     # mismo bloque del evento -> cautela ALTA
WINDOW_MED_H    = 24    # día previo -> cautela MEDIA


def _first_friday(year: int, month: int) -> datetime:
    """Primer viernes del mes — fecha aproximada del NFP (US Non-Farm Payrolls)."""
    d = datetime(year, month, 1, tzinfo=timezone.utc)
    # weekday(): lunes=0 ... viernes=4
    offset = (4 - d.weekday()) % 7
    return d + timedelta(days=offset)


def _upcoming_events(now: datetime, days_ahead: int = 10):
    """
    Devuelve lista de eventos de alto impacto en [now - 1d, now + days_ahead],
    cada uno como dict {name, dt, impact}.
    """
    events = []

    # FOMC (impacto MUY alto en GOLD)
    for ds in FOMC_2026:
        dt = datetime.strptime(ds, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dt += timedelta(hours=FOMC_STATEMENT_HOUR_UTC)
        events.append({"name": "FOMC (decisión Fed)", "dt": dt, "impact": "MUY ALTO"})

    # NFP — primer viernes de este mes y del siguiente
    for mshift in (0, 1):
        y, m = now.year, now.month + mshift
        if m > 12:
            y, m = y + 1, m - 12
        nfp = _first_friday(y, m) + timedelta(hours=US_DATA_HOUR_UTC)
        events.append({"name": "NFP (empleo USA)", "dt": nfp, "impact": "ALTO"})

    lo = now - timedelta(days=1)
    hi = now + timedelta(days=days_ahead)
    return sorted([e for e in events if lo <= e["dt"] <= hi], key=lambda e: e["dt"])


def macro_context(now: datetime = None, days_ahead: int = 45) -> dict:
    """
    Punto de entrada para los monitores.

    Devuelve:
      caution   : 'ALTA' | 'MEDIA' | 'BAJA'
      message   : str legible para mostrar
      next      : dict del próximo evento (o None)
      upcoming  : lista de eventos próximos
    """
    if now is None:
        now = datetime.now(timezone.utc)

    upcoming = _upcoming_events(now, days_ahead)
    caution, msg, nxt = "BAJA", "Sin eventos macro de alto impacto a la vista.", None

    for e in upcoming:
        hours = (e["dt"] - now).total_seconds() / 3600.0
        if -WINDOW_HIGH_H <= hours <= WINDOW_HIGH_H:
            caution = "ALTA"
            when = "EN CURSO/inminente" if hours >= 0 else "hace " + str(round(-hours, 1)) + "h"
            msg = ("[!] " + e["name"] + " (" + e["impact"] + ") " + when
                   + " — volatilidad extrema esperada. Señales técnicas menos fiables. "
                   + "Contexto, NUNCA trigger.")
            nxt = e
            break

    if caution == "BAJA":
        future = [e for e in upcoming if e["dt"] >= now]
        if future:
            e = future[0]
            hours = (e["dt"] - now).total_seconds() / 3600.0
            nxt = e
            if hours <= WINDOW_MED_H:
                caution = "MEDIA"
                msg = ("[!] " + e["name"] + " (" + e["impact"] + ") en "
                       + str(round(hours, 1)) + "h ("
                       + e["dt"].strftime("%d-%b %H:%M") + " UTC). Cautela: evitar "
                       + "sobre-interpretar señales justo antes. Contexto, no trigger.")
            else:
                days = hours / 24.0
                msg = ("Próximo evento alto impacto: " + e["name"] + " en "
                       + str(round(days, 1)) + " días ("
                       + e["dt"].strftime("%d-%b %H:%M") + " UTC).")

    return {"caution": caution, "message": msg, "next": nxt, "upcoming": upcoming}


# ── Capa 2: Watchlist para revisión de noticias en vivo (Claude + WebSearch) ─
# Temas y FUENTES OFICIALES a revisar en el reporte diario y briefing semanal.
# El agente NUNCA opera por esto; solo lo añade como contexto interpretativo.
MACRO_WATCHLIST = {
    "fuentes_oficiales": [
        "federalreserve.gov",        # Fed: política monetaria, discursos
        "treasury.gov",              # Tesoro USA
        "bls.gov",                   # datos de empleo/inflación
        "whitehouse.gov",            # acciones/órdenes ejecutivas firmadas
    ],
    "temas_seguimiento": [
        "Decisiones y discursos de la Fed (tono hawkish/dovish)",
        "Acuerdos/sanciones geopolíticas firmadas (ej. EE.UU.-Irán, Rusia-Ucrania)",
        "Cambios de aranceles / comercio (afectan USD y oro como refugio)",
        "Datos macro USA: CPI, NFP, PCE, PIB",
        "Movimientos del DXY (dólar) y rendimientos del Treasury 10Y (inversos al oro)",
        "Petróleo (correlación con inflación y riesgo geopolítico)",
    ],
    "como_afecta_al_oro": (
        "Oro = refugio. Sube con: tensión geopolítica, Fed dovish (bajadas de tipos), "
        "dólar débil, rendimientos a la baja, inflación alta. Baja con: paz/acuerdos, "
        "Fed hawkish (subidas), dólar fuerte, rendimientos al alza. "
        "OJO: la reacción inicial a una noticia suele revertirse — por eso operamos "
        "SIEMPRE por técnico y usamos la noticia solo para entender el porqué."
    ),
}


if __name__ == "__main__":
    ctx = macro_context()
    print("=" * 55)
    print("MACRO CONTEXT | " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M") + " UTC")
    print("=" * 55)
    print("Cautela: " + ctx["caution"])
    print(ctx["message"])
    print()
    print("Próximos eventos de alto impacto:")
    for e in ctx["upcoming"]:
        print("  " + e["dt"].strftime("%d-%b %H:%M") + " UTC | "
              + e["name"] + " (" + e["impact"] + ")")
