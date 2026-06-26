# -*- coding: utf-8 -*-
"""
Aurex — Wrapper de ejecucion con observabilidad (B2)
====================================================
Ejecuta un monitor como subproceso y registra de forma estructurada:
inicio, duracion, codigo de salida, y deteccion de errores (timeouts de
login, tracebacks, "sin trade", apertura de trade). Re-emite la salida del
monitor por pantalla para que el cron siga mostrandola igual que ahora.

CLAVE: NO modifica el codigo de los monitores. Cero riesgo para el trading.
Solo aporta trazabilidad y captura de fallos silenciosos.

Uso:
  python run_monitor.py monitor_m15_obs.py
  python run_monitor.py monitor_scalp.py
  python run_monitor.py monitor_swing.py
"""
import os
import sys
import time
import subprocess

from aurex_logger import get_logger

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Patrones que indican estados relevantes en la salida del monitor.
ERR_PATTERNS = (
    'Login fallido', 'Login error', 'Read timed out', 'Traceback',
    'ERROR', 'Exception', 'Max retries',
)
TRADE_PATTERNS = ('ABIERTA OK', 'ABRIENDO', 'Abriendo posicion', 'AUTO-CIERRE',
                  '[AUTO-CIERRE')


def main():
    if len(sys.argv) < 2:
        print('Uso: python run_monitor.py <monitor.py>')
        sys.exit(2)

    monitor = sys.argv[1]
    name = os.path.splitext(os.path.basename(monitor))[0]
    log = get_logger(name)

    script = os.path.join(BASE_DIR, monitor)
    if not os.path.isfile(script):
        log.error('monitor no encontrado: ' + monitor)
        print('ERROR: monitor no encontrado: ' + monitor)
        sys.exit(2)

    log.info('START ' + monitor)
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, script],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = (proc.stdout or '') + (proc.stderr or '')
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        dur = round(time.time() - t0, 1)
        log.error('TIMEOUT tras ' + str(dur) + 's ejecutando ' + monitor)
        print('ERROR: el monitor ' + monitor + ' supero el timeout (180s)')
        sys.exit(1)

    dur = round(time.time() - t0, 1)

    # Re-emitir salida para el cron / usuario
    sys.stdout.write(out)
    sys.stdout.flush()

    # Clasificar resultado
    had_error = (rc != 0) or any(p in out for p in ERR_PATTERNS)
    had_trade = any(p in out for p in TRADE_PATTERNS)

    summary = 'END ' + monitor + ' | rc=' + str(rc) + ' | ' + str(dur) + 's'
    if had_trade:
        summary += ' | EVENTO_TRADE'
    if had_error:
        # Extraer la primera linea relevante para el log
        first = next((ln.strip() for ln in out.splitlines()
                      if any(p in ln for p in ERR_PATTERNS)), 'rc!=0')
        log.error(summary + ' | ' + first)
    else:
        log.info(summary)

    sys.exit(rc)


if __name__ == '__main__':
    main()
