# -*- coding: utf-8 -*-
"""
Aurex — Dashboard v1 (Fase 2)
=============================
Panel local de SOLO LECTURA: muestra estado de cuenta, posiciones, historial
real del broker (tabla trade_closes de la reconciliacion), curva de P&L y
salud del sistema. CERO botones de accion: ver, no tocar.

No expone secretos. Solo escucha en localhost.

Uso:  python dashboard.py   ->  http://localhost:8181
"""
import os
import re
import sys
import time
import sqlite3
from datetime import datetime, timezone

os.environ.setdefault('CAPITAL_MODE', 'REAL')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, render_template_string
from capital_client import CapitalClient

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, 'aurex_trades.db')
LOG_DIR = os.path.join(BASE, 'logs')

app = Flask(__name__)
_client = CapitalClient()
_cache = {'ts': 0.0, 'data': None}
CACHE_SEC = 20  # no marear al broker


def _monitor_health():
    """Ultima ejecucion OK de cada monitor segun el log mensual (B2)."""
    out = {}
    try:
        fname = 'aurex_' + datetime.now(timezone.utc).strftime('%Y-%m') + '.log'
        path = os.path.join(LOG_DIR, fname)
        if not os.path.isfile(path):
            return out
        with open(path, encoding='utf-8', errors='replace') as f:
            lines = f.readlines()[-400:]
        # Formato: '2026-07-02 11:22:20 UTC | INFO | aurex.monitor_m15_obs | END monitor_m15_obs.py | rc=0 | 3.2s'
        pat = re.compile(
            r'^(\S+ \S+) UTC \|.*\| aurex\.(monitor_[a-z0-9_]+) \| END .*rc=(\d+)')
        for ln in lines:
            m = pat.match(ln)
            if m:
                ts, mon, rc = m.group(1), m.group(2), m.group(3)
                out[mon] = {'last_end': ts, 'ok': rc == '0'}
    except Exception:
        pass
    return out


def _last_signals(n=6):
    """Ultimas filas de los signal logs (senales/trades recientes)."""
    import csv
    rows = []
    for fname, nivel in (('m15_signal_log.csv', 'M15'), ('swing_signal_log.csv', 'SWING')):
        p = os.path.join(BASE, fname)
        if not os.path.isfile(p):
            continue
        try:
            with open(p, newline='', encoding='utf-8') as f:
                for r in list(csv.DictReader(f))[-n:]:
                    rows.append({
                        'nivel': nivel,
                        'fecha': r.get('datetime_utc', ''),
                        'dir': r.get('direction', ''),
                        'entry': r.get('entry_price', ''),
                        'resultado': (r.get('resultado', '') or '')[:24],
                        'pnl': r.get('pnl_teorico_usd', ''),
                    })
        except Exception:
            continue
    rows.sort(key=lambda x: x['fecha'], reverse=True)
    return rows[:n]


def _broker_truth():
    """Historial real (reconciliacion) + curva de P&L acumulado."""
    out = {'closes': [], 'curve': [], 'total_pnl': 0.0, 'wr': None, 'pf': None, 'n': 0}
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT date_utc, pnl FROM trade_closes "
            "WHERE tx_type='TRADE' AND instrument='GOLD' ORDER BY date_utc").fetchall()
        conn.close()
        acc = 0.0
        wins = losses = 0
        gross_w = gross_l = 0.0
        for d, p in rows:
            acc += p
            out['curve'].append({'t': str(d)[:10], 'v': round(acc, 2)})
            if p > 0.01:
                wins += 1; gross_w += p
            elif p < -0.01:
                losses += 1; gross_l += abs(p)
        out['n'] = len(rows)
        out['total_pnl'] = round(acc, 2)
        if wins + losses:
            out['wr'] = round(100 * wins / (wins + losses), 1)
        if gross_l:
            out['pf'] = round(gross_w / gross_l, 2)
        out['closes'] = [
            {'fecha': str(d)[:16].replace('T', ' '), 'pnl': round(p, 2)}
            for d, p in rows[-8:]
        ][::-1]
    except Exception:
        pass
    return out


def build_status():
    now = time.time()
    if _cache['data'] and now - _cache['ts'] < CACHE_SEC:
        return _cache['data']

    balance, positions, precio = None, [], None
    broker_ok = False
    try:
        if _client.ensure_session():
            broker_ok = True
            balance = _client.get_balance()
            for p in _client.get_positions():
                positions.append({
                    'epic': p.get('epic'),
                    'dir': p.get('direction'),
                    'size': p.get('size'),
                    'entry': p.get('entry_price'),
                    'sl': p.get('stop_loss'),
                    'tp': p.get('take_profit'),
                    'pnl': p.get('profit_loss'),
                    'aurex': p.get('epic') == 'GOLD',
                })
            df = _client.get_prices('GOLD', 'MINUTE_15', 3)
            if df is not None and len(df):
                precio = float(df['close'].iloc[-1])
    except Exception:
        pass

    gold_open = any(p['aurex'] for p in positions)
    estado = 'OPERANDO — posicion GOLD abierta' if gold_open else 'OPERATIVO — esperando senal'
    if not broker_ok:
        estado = 'ERROR — sin conexion con broker'

    data = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'estado': estado,
        'broker_ok': broker_ok,
        'precio_gold': precio,
        'balance': balance,
        'positions': positions,
        'signals': _last_signals(),
        'truth': _broker_truth(),
        'monitors': _monitor_health(),
        'moneda': 'EUR',
    }
    _cache['data'] = data
    _cache['ts'] = now
    return data


@app.route('/api/status')
def api_status():
    return jsonify(build_status())


PAGE = """
<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Aurex — Panel</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root { --bg:#0d1117; --card:#161b22; --line:#30363d; --tx:#e6edf3;
          --dim:#8b949e; --green:#3fb950; --red:#f85149; --gold:#e3b341; }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--tx);
         font:14px/1.5 -apple-system,'Segoe UI',sans-serif; padding:18px; }
  .wrap { max-width:880px; margin:0 auto; display:grid; gap:14px; }
  .card { background:var(--card); border:1px solid var(--line);
          border-radius:10px; padding:16px; }
  h1 { font-size:19px; display:flex; align-items:center; gap:10px; }
  h2 { font-size:13px; color:var(--dim); text-transform:uppercase;
       letter-spacing:.06em; margin-bottom:10px; }
  .dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
  .ok { background:var(--green); } .bad { background:var(--red); }
  .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:10px; }
  .kpi .v { font-size:21px; font-weight:600; } .kpi .l { color:var(--dim); font-size:12px; }
  .pos { color:var(--green); } .neg { color:var(--red); } .gold { color:var(--gold); }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  td,th { padding:5px 8px; text-align:left; border-bottom:1px solid var(--line); }
  th { color:var(--dim); font-weight:500; }
  .tag { font-size:11px; padding:1px 7px; border-radius:99px;
         border:1px solid var(--line); color:var(--dim); }
  .muted { color:var(--dim); font-size:12px; }
</style></head><body><div class="wrap">

<div class="card"><h1><span id="dot" class="dot ok"></span> AUREX
  <span id="estado" class="muted"></span></h1>
  <div class="muted" id="updated"></div></div>

<div class="card"><h2>Cuenta</h2><div class="grid">
  <div class="kpi"><div class="v" id="equity">—</div><div class="l">Equity (EUR)</div></div>
  <div class="kpi"><div class="v" id="disponible">—</div><div class="l">Disponible</div></div>
  <div class="kpi"><div class="v" id="flotante">—</div><div class="l">P&L flotante</div></div>
  <div class="kpi"><div class="v gold" id="precio">—</div><div class="l">GOLD</div></div>
</div></div>

<div class="card"><h2>Posiciones</h2><div id="positions"></div></div>

<div class="card"><h2>Resultados reales (verdad del broker)</h2>
  <div class="grid" style="margin-bottom:10px">
    <div class="kpi"><div class="v" id="tpnl">—</div><div class="l">P&L trades (EUR)</div></div>
    <div class="kpi"><div class="v" id="wr">—</div><div class="l">Win rate</div></div>
    <div class="kpi"><div class="v" id="pf">—</div><div class="l">Profit factor</div></div>
    <div class="kpi"><div class="v" id="ntr">—</div><div class="l">Trades cerrados</div></div>
  </div>
  <canvas id="curve" height="90"></canvas>
  <div id="closes" style="margin-top:10px"></div></div>

<div class="card"><h2>Señales recientes</h2><div id="signals"></div></div>

<div class="card"><h2>Sistema</h2><div id="monitors"></div>
  <div class="muted" style="margin-top:8px">Panel de solo lectura · sin acciones
  · actualiza cada 30 s · datos del broker cacheados 20 s</div></div>

</div><script>
let chart;
function money(v){ if(v==null||v==='')return '—';
  const n=+v; return (n>=0?'+':'')+n.toFixed(2); }
function cls(v){ return +v>=0?'pos':'neg'; }
async function refresh(){
  const r = await fetch('/api/status'); const d = await r.json();
  document.getElementById('estado').textContent = d.estado;
  document.getElementById('updated').textContent = 'Actualizado: '+d.updated;
  document.getElementById('dot').className = 'dot '+(d.broker_ok?'ok':'bad');
  if(d.balance){
    document.getElementById('equity').textContent = (+d.balance.balance).toFixed(2);
    document.getElementById('disponible').textContent = (+d.balance.available).toFixed(2);
    const f = document.getElementById('flotante');
    f.textContent = money(d.balance.profit_loss); f.className='v '+cls(d.balance.profit_loss);
  }
  if(d.precio_gold) document.getElementById('precio').textContent = d.precio_gold.toFixed(2);
  // posiciones
  let ph = '';
  if(!d.positions.length) ph = '<div class="muted">Sin posiciones — flat.</div>';
  else { ph = '<table><tr><th></th><th>Dir</th><th>Size</th><th>Entrada</th><th>SL</th><th>TP</th><th>P&L</th></tr>';
    for(const p of d.positions){
      ph += `<tr><td>${p.epic} ${p.aurex?'':'<span class="tag">manual</span>'}</td>
      <td>${p.dir}</td><td>${p.size}</td><td>${p.entry??'—'}</td>
      <td>${p.sl||'<span class="neg">sin SL</span>'}</td><td>${p.tp||'—'}</td>
      <td class="${cls(p.pnl)}">${money(p.pnl)}</td></tr>`; }
    ph += '</table>'; }
  document.getElementById('positions').innerHTML = ph;
  // verdad broker
  const t = d.truth;
  document.getElementById('tpnl').textContent = money(t.total_pnl);
  document.getElementById('tpnl').className = 'v '+cls(t.total_pnl);
  document.getElementById('wr').textContent = t.wr!=null? t.wr+'%':'—';
  document.getElementById('pf').textContent = t.pf??'—';
  document.getElementById('ntr').textContent = t.n;
  let ch=''; if(t.closes.length){
    ch='<table><tr><th>Cierre</th><th>P&L (EUR)</th></tr>';
    for(const c of t.closes) ch+=`<tr><td>${c.fecha}</td>
      <td class="${cls(c.pnl)}">${money(c.pnl)}</td></tr>`;
    ch+='</table>'; }
  document.getElementById('closes').innerHTML = ch;
  const labels=t.curve.map(x=>x.t), vals=t.curve.map(x=>x.v);
  if(!chart){ chart = new Chart(document.getElementById('curve'),{type:'line',
    data:{labels,datasets:[{data:vals,borderColor:'#e3b341',borderWidth:2,
      pointRadius:0,fill:{target:'origin',above:'rgba(227,179,65,.08)'}}]},
    options:{plugins:{legend:{display:false}},scales:{x:{ticks:{color:'#8b949e',
      maxTicksLimit:8}},y:{ticks:{color:'#8b949e'}}}}});
  } else { chart.data.labels=labels; chart.data.datasets[0].data=vals; chart.update(); }
  // senales
  let sh='<table><tr><th>Nivel</th><th>Fecha UTC</th><th>Dir</th><th>Entrada</th><th>Resultado</th><th>P&L est.</th></tr>';
  for(const s of d.signals) sh+=`<tr><td>${s.nivel}</td><td>${s.fecha}</td>
    <td>${s.dir}</td><td>${s.entry}</td><td>${s.resultado}</td><td>${s.pnl}</td></tr>`;
  document.getElementById('signals').innerHTML = sh+'</table>';
  // monitores
  let mh='<table><tr><th>Monitor</th><th>Última ejecución OK</th><th>Estado</th></tr>';
  const mons = Object.entries(d.monitors);
  if(!mons.length) mh += '<tr><td colspan=3 class="muted">sin registros hoy</td></tr>';
  for(const [k,v] of mons) mh+=`<tr><td>${k}</td><td>${v.last_end}</td>
    <td>${v.ok?'<span class="pos">OK</span>':'<span class="neg">ERROR</span>'}</td></tr>`;
  document.getElementById('monitors').innerHTML = mh+'</table>';
}
refresh(); setInterval(refresh, 30000);
</script></body></html>
"""


@app.route('/')
def index():
    return render_template_string(PAGE)


if __name__ == '__main__':
    print('Aurex Dashboard v1 (solo lectura) -> http://localhost:8181')
    app.run(host='127.0.0.1', port=8181, debug=False)
