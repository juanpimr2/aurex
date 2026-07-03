# -*- coding: utf-8 -*-
"""
Aurex — Health Check (agente auditor, capa determinista)
=========================================================
SOLO LECTURA. Revisa la salud del sistema y emite un informe con veredicto.
Es la base del "agente auditor": este script detecta, Claude interpreta.
NO toma decisiones de trading ni modifica nada.

Chequea:
  1. Frescura de monitores (logs B2): ¿corrieron recientemente? ¿errores?
  2. Broker: login, balance, posiciones (¿posicion Aurex sin SL?)
  3. Datos: velas acumuladas hoy, BD accesible, reconciliacion actualizada
  4. Riesgo: drawdown del equity vs pico historico de trade_closes
  5. Integridad: ultimo backup verificable

Salida: informe legible + exit code (0=OK, 1=WARN, 2=CRIT).
Uso: python health_check.py
"""
import os
import re
import sys
import sqlite3
from datetime import datetime, timedelta, timezone

os.environ.setdefault('CAPITAL_MODE', 'REAL')
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

DB_PATH = os.path.join(BASE, 'aurex_trades.db')
LOG_DIR = os.path.join(BASE, 'logs')

ISSUES = []   # (nivel, mensaje)  nivel: WARN | CRIT
OK = []


def ok(msg):
    OK.append(msg)


def warn(msg):
    ISSUES.append(('WARN', msg))


def crit(msg):
    ISSUES.append(('CRIT', msg))


def check_monitors():
    """Monitores: ultima ejecucion y errores en el log mensual."""
    now = datetime.now(timezone.utc)
    fname = 'aurex_' + now.strftime('%Y-%m') + '.log'
    path = os.path.join(LOG_DIR, fname)
    if not os.path.isfile(path):
        warn('Sin log mensual (' + fname + ') — ¿monitores corriendo?')
        return
    with open(path, encoding='utf-8', errors='replace') as f:
        lines = f.readlines()[-600:]
    pat = re.compile(r'^(\S+ \S+) UTC \|\s*(\w+)\s*\| aurex\.(monitor_[a-z0-9_]+) \| END .*rc=(\d+)')
    last = {}
    errores = 0
    for ln in lines:
        m = pat.match(ln)
        if m:
            last[m.group(3)] = (m.group(1), m.group(4))
        if '| ERROR' in ln:
            errores += 1
    # es fin de semana? (mercado cerrado sab/dom)
    weekend = now.weekday() >= 5
    umbrales = {'monitor_m15_obs': 40, 'monitor_scalp': 70, 'monitor_swing': 60 * 26}
    for mon, mins in umbrales.items():
        if mon not in last:
            (warn if weekend else crit)('Monitor ' + mon + ' sin ejecuciones registradas este mes')
            continue
        ts, rc = last[mon]
        age = (now - datetime.strptime(ts, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)).total_seconds() / 60
        if rc != '0':
            crit(mon + ': ultima ejecucion con ERROR (rc=' + rc + ')')
        elif age > mins and not weekend:
            warn(mon + ': sin correr hace ' + str(int(age)) + ' min (umbral ' + str(mins) + ')')
        else:
            ok(mon + ' OK (hace ' + str(int(age)) + ' min)')
    if errores:
        warn(str(errores) + ' lineas ERROR en el log mensual (revisar)')


def check_broker():
    """Broker accesible y posiciones protegidas."""
    try:
        from capital_client import CapitalClient
        c = CapitalClient()
        if not c.login():
            crit('Login al broker FALLIDO')
            return None
        bal = c.get_balance()
        if not bal:
            crit('Balance no disponible')
            return None
        ok('Broker OK — equity %.2f EUR' % bal['balance'])
        for p in c.get_positions():
            if p.get('epic') == 'GOLD':
                sl, tp = p.get('stop_loss'), p.get('take_profit')
                if not sl or not tp:
                    crit('POSICION GOLD SIN SL/TP EN BROKER — riesgo descubierto')
                else:
                    ok('Posicion GOLD protegida (SL %.2f / TP %.2f)' % (sl, tp))
        return bal['balance']
    except Exception as e:
        crit('Excepcion consultando broker: ' + str(e))
        return None


def check_data():
    """BD, velas acumuladas y reconciliacion."""
    if not os.path.isfile(DB_PATH):
        crit('BD aurex_trades.db no existe')
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        tablas = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for t in ('trades', 'candles', 'trade_closes'):
            if t not in tablas:
                warn('Tabla ' + t + ' ausente en BD')
        if 'candles' in tablas:
            row = conn.execute(
                "SELECT MAX(timestamp) FROM candles WHERE tf='MINUTE_15'").fetchone()
            if row and row[0]:
                age_h = (datetime.now(timezone.utc).replace(tzinfo=None)
                         - datetime.fromisoformat(str(row[0]))).total_seconds() / 3600
                if age_h > 30:
                    warn('Velas M15: ultima de hace %.0f h (collector diario?)' % age_h)
                else:
                    ok('Velas acumulandose (ultima M15 hace %.1f h)' % age_h)
        if 'trade_closes' in tablas:
            n = conn.execute("SELECT COUNT(*) FROM trade_closes").fetchone()[0]
            last = conn.execute("SELECT MAX(date_utc) FROM trade_closes").fetchone()[0]
            ok('Reconciliacion: ' + str(n) + ' registros (ultimo ' + str(last)[:10] + ')')
    finally:
        conn.close()


def check_risk(equity):
    """Drawdown del equity vs pico (aprox: P&L acumulado + depositos)."""
    if equity is None or not os.path.isfile(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT date_utc, pnl, tx_type FROM trade_closes ORDER BY date_utc").fetchall()
    finally:
        conn.close()
    acc, peak = 0.0, 0.0
    for _, p, ttype in rows:
        if ttype in ('TRADE', 'DEPOSIT', 'WITHDRAWAL', 'TRANSFER'):
            acc += p
        peak = max(peak, acc)
    # dd relativo del equity actual vs maximo teorico reciente
    if peak > 0 and equity < peak:
        dd = 100 * (peak - equity) / peak
        if dd > 15:
            crit('Drawdown equity vs pico: %.1f%% (>15%%)' % dd)
        elif dd > 8:
            warn('Drawdown equity vs pico: %.1f%%' % dd)
        else:
            ok('Drawdown contenido (%.1f%% vs pico)' % dd)


def check_backup():
    bdir = os.path.join(BASE, 'backups')
    if not os.path.isdir(bdir):
        warn('Sin carpeta backups/')
        return
    items = sorted(d for d in os.listdir(bdir) if d.startswith('aurex_backup_'))
    if not items:
        warn('Sin backups')
        return
    last = items[-1]
    ts = datetime.strptime(last.replace('aurex_backup_', ''), '%Y%m%d_%H%M%S')
    age_h = (datetime.now() - ts).total_seconds() / 3600
    if age_h > 30:
        warn('Ultimo backup hace %.0f h' % age_h)
    else:
        ok('Backup reciente (' + last + ')')


def main():
    print('=' * 64)
    print('AUREX HEALTH CHECK | ' + datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))
    print('=' * 64)
    check_monitors()
    equity = check_broker()
    check_data()
    check_risk(equity)
    check_backup()

    print()
    for msg in OK:
        print('  [OK]   ' + msg)
    for lvl, msg in ISSUES:
        print('  [' + lvl + '] ' + msg)

    crits = [m for l, m in ISSUES if l == 'CRIT']
    warns = [m for l, m in ISSUES if l == 'WARN']
    print()
    if crits:
        print('VEREDICTO: CRITICO — ' + str(len(crits)) + ' problema(s) grave(s)')
        sys.exit(2)
    elif warns:
        print('VEREDICTO: AVISOS — ' + str(len(warns)) + ' aviso(s), operativa puede continuar')
        sys.exit(1)
    else:
        print('VEREDICTO: SANO — todos los chequeos en verde')
        sys.exit(0)


if __name__ == '__main__':
    main()
