# -*- coding: utf-8 -*-
"""
Aurex — Dashboard v1.1 "Bóveda" (Fase 2)
========================================
Panel local de SOLO LECTURA: estado de cuenta, posiciones, historial real del
broker (tabla trade_closes de la reconciliación), curva de P&L y salud del
sistema. CERO botones de acción: ver, no tocar.

Estética: bóveda suiza x terminal — obsidiana, oro 999.9, Marcellus + Plex Mono.
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
        # '2026-07-02 11:22:20 UTC | INFO | aurex.monitor_m15_obs | END ... | rc=0 | 3.2s'
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
    estado = 'OPERANDO — posición GOLD abierta' if gold_open else 'OPERATIVO — esperando señal'
    if not broker_ok:
        estado = 'ERROR — sin conexión con broker'

    data = {
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
        'estado': estado,
        'broker_ok': broker_ok,
        'gold_open': gold_open,
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


PAGE = r"""
<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>AUREX · Bóveda</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Marcellus&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root{
  --obsidian:#0b0a08; --pit:#070605; --card:#12100c; --card2:#161310;
  --line:#2a2419; --line-gold:#3d3320;
  --gold:#d4af37; --gold-hi:#f3d878; --gold-dim:#8a7434;
  --tx:#ece5d3; --dim:#9c917a; --faint:#5f584a;
  --up:#7fd6a4; --down:#e5646a;
}
*{box-sizing:border-box;margin:0;padding:0}
::selection{background:var(--gold);color:#0b0a08}
html{scrollbar-color:var(--line-gold) var(--pit)}
body{
  background:var(--obsidian); color:var(--tx);
  font:14px/1.55 'IBM Plex Mono',monospace;
  min-height:100vh; padding:26px 18px 40px;
  background-image:
    radial-gradient(ellipse 900px 420px at 50% -80px, rgba(212,175,55,.09), transparent 60%),
    radial-gradient(ellipse 1400px 800px at 50% 120%, rgba(0,0,0,.5), transparent);
}
/* grano sutil */
body::before{content:'';position:fixed;inset:0;pointer-events:none;opacity:.05;z-index:9;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence baseFrequency='.85' numOctaves='2'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)' opacity='.6'/%3E%3C/svg%3E");}
/* hairline dorada superior */
body::after{content:'';position:fixed;top:0;left:0;right:0;height:1px;z-index:10;
  background:linear-gradient(90deg,transparent,var(--gold) 30%,var(--gold-hi) 50%,var(--gold) 70%,transparent);}
.wrap{max-width:920px;margin:0 auto;display:grid;gap:16px}

/* ── cabecera ── */
header.card{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px}
.brand{display:flex;align-items:center;gap:16px}
.wordmark{
  font-family:'Marcellus',serif; font-size:34px; letter-spacing:.34em; line-height:1;
  background:linear-gradient(100deg,#9a7d2e 0%,var(--gold) 25%,var(--gold-hi) 50%,var(--gold) 75%,#9a7d2e 100%);
  background-size:200% 100%;
  -webkit-background-clip:text; background-clip:text; color:transparent;
  animation:shimmer 7s linear infinite; padding-right:.34em;
}
@keyframes shimmer{to{background-position:-200% 0}}
.hallmark{
  font-size:9.5px;letter-spacing:.22em;color:var(--gold-dim);
  border:1px solid var(--line-gold);padding:5px 9px;border-radius:2px;white-space:nowrap;
}
.status{display:flex;align-items:center;gap:10px;font-size:12.5px;letter-spacing:.05em;color:var(--dim)}
.pulse{position:relative;width:9px;height:9px;border-radius:50%;background:var(--gold)}
.pulse::after{content:'';position:absolute;inset:-5px;border-radius:50%;
  border:1px solid var(--gold);animation:ring 2.2s ease-out infinite}
.pulse.bad{background:var(--down)} .pulse.bad::after{border-color:var(--down)}
.pulse.live{background:var(--up)} .pulse.live::after{border-color:var(--up)}
@keyframes ring{0%{transform:scale(.5);opacity:.9}100%{transform:scale(1.9);opacity:0}}
.updated{font-size:10.5px;color:var(--faint);letter-spacing:.08em;width:100%;text-align:right}

/* ── tarjetas placa de bóveda ── */
.card{position:relative;background:linear-gradient(180deg,var(--card2),var(--card));
  border:1px solid var(--line);border-radius:3px;padding:20px 22px;
  animation:reveal .7s cubic-bezier(.2,.7,.3,1) both}
.card:nth-child(2){animation-delay:.06s}.card:nth-child(3){animation-delay:.12s}
.card:nth-child(4){animation-delay:.18s}.card:nth-child(5){animation-delay:.24s}
.card:nth-child(6){animation-delay:.3s}
@keyframes reveal{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
/* esquinas grabadas art-decó */
.card i.c{position:absolute;width:9px;height:9px;border:1px solid var(--gold-dim);pointer-events:none}
.card i.c1{top:5px;left:5px;border-right:0;border-bottom:0}
.card i.c2{top:5px;right:5px;border-left:0;border-bottom:0}
.card i.c3{bottom:5px;left:5px;border-right:0;border-top:0}
.card i.c4{bottom:5px;right:5px;border-left:0;border-top:0}

h2{font-family:'Marcellus',serif;font-size:13px;font-weight:400;color:var(--gold);
  letter-spacing:.28em;text-transform:uppercase;margin-bottom:14px;
  display:flex;align-items:center;gap:12px}
h2::after{content:'';flex:1;height:1px;
  background:linear-gradient(90deg,var(--line-gold),transparent)}
h2 .dia{color:var(--gold-dim);font-size:8px}

/* ── KPIs ── */
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:14px}
.kpi{border-left:1px solid var(--line-gold);padding-left:14px}
.kpi .v{font-size:24px;font-weight:600;letter-spacing:-.01em;font-variant-numeric:tabular-nums;
  transition:color .4s}
.kpi .l{color:var(--faint);font-size:10px;letter-spacing:.16em;text-transform:uppercase;margin-top:3px}
.pos{color:var(--up)} .neg{color:var(--down)} .goldtx{color:var(--gold-hi)}
.kpi .v.flash{animation:flash .8s}
@keyframes flash{0%{color:var(--gold-hi)}100%{}}

/* ── tablas ── */
table{width:100%;border-collapse:collapse;font-size:12.5px;font-variant-numeric:tabular-nums}
td,th{padding:7px 10px;text-align:left;border-bottom:1px solid var(--line)}
th{color:var(--faint);font-weight:500;font-size:10px;letter-spacing:.14em;text-transform:uppercase}
tbody tr{transition:background .25s}
tbody tr:hover{background:rgba(212,175,55,.045)}
tr:last-child td{border-bottom:0}
.tag{font-size:9px;letter-spacing:.12em;padding:2px 7px;border-radius:2px;
  border:1px solid var(--line-gold);color:var(--gold-dim);text-transform:uppercase}
.muted{color:var(--faint);font-size:11.5px;letter-spacing:.04em}
.empty{color:var(--faint);font-size:12px;padding:6px 0;letter-spacing:.06em}
.empty b{color:var(--gold-dim);font-weight:500}

/* precio oro destacado */
.xau{display:flex;align-items:baseline;gap:8px}
.xau .sym{font-family:'Marcellus',serif;color:var(--gold-dim);font-size:12px;letter-spacing:.2em}

canvas{margin-top:4px}
footer{color:var(--faint);font-size:9.5px;letter-spacing:.26em;text-align:center;
  text-transform:uppercase;margin-top:6px}
footer b{color:var(--gold-dim);font-weight:400}
@media(max-width:560px){.wordmark{font-size:24px}.card{padding:16px}}
</style></head><body><div class="wrap">

<header class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <div class="brand">
    <div class="wordmark">AUREX</div>
    <div class="hallmark">XAU · 999.9<br>CAPITAL.COM</div>
  </div>
  <div class="status"><span id="dot" class="pulse"></span><span id="estado">conectando…</span></div>
  <div class="updated" id="updated"></div>
</header>

<section class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <h2><span class="dia">◆</span> Cuenta</h2>
  <div class="grid">
    <div class="kpi"><div class="v goldtx" id="equity">—</div><div class="l">Equity · EUR</div></div>
    <div class="kpi"><div class="v" id="disponible">—</div><div class="l">Disponible</div></div>
    <div class="kpi"><div class="v" id="flotante">—</div><div class="l">P&L flotante</div></div>
    <div class="kpi"><div class="v goldtx xau"><span id="precio">—</span><span class="sym">XAU</span></div>
      <div class="l">Oro · spot</div></div>
  </div>
</section>

<section class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <h2><span class="dia">◆</span> Posiciones</h2><div id="positions"></div>
</section>

<section class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <h2><span class="dia">◆</span> Libro real del broker</h2>
  <div class="grid" style="margin-bottom:14px">
    <div class="kpi"><div class="v" id="tpnl">—</div><div class="l">P&L trades · EUR</div></div>
    <div class="kpi"><div class="v" id="wr">—</div><div class="l">Win rate</div></div>
    <div class="kpi"><div class="v" id="pf">—</div><div class="l">Profit factor</div></div>
    <div class="kpi"><div class="v" id="ntr">—</div><div class="l">Trades cerrados</div></div>
  </div>
  <canvas id="curve" height="92"></canvas>
  <div id="closes" style="margin-top:12px"></div>
</section>

<section class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <h2><span class="dia">◆</span> Señales recientes</h2><div id="signals"></div>
</section>

<section class="card"><i class="c c1"></i><i class="c c2"></i><i class="c c3"></i><i class="c c4"></i>
  <h2><span class="dia">◆</span> Sistema</h2><div id="monitors"></div>
  <div class="muted" style="margin-top:10px">Solo lectura · sin acciones · refresco 30 s · broker cacheado 20 s</div>
</section>

<footer>Aurex <b>◆</b> panel de bóveda <b>◆</b> ver, no tocar</footer>

</div><script>
let chart, prevEquity=null;
const $=id=>document.getElementById(id);
function money(v){if(v==null||v==='')return '—';const n=+v;return (n>=0?'+':'')+n.toFixed(2);}
function cls(v){return +v>=0?'pos':'neg';}
async function refresh(){
  let d; try{ d = await (await fetch('/api/status')).json(); }catch(e){ return; }
  $('estado').textContent = d.estado;
  $('updated').textContent = d.updated;
  $('dot').className = 'pulse ' + (!d.broker_ok?'bad': d.gold_open?'live':'');
  if(d.balance){
    const eq=(+d.balance.balance).toFixed(2);
    if(prevEquity!==null && eq!==prevEquity){$('equity').classList.remove('flash');void $('equity').offsetWidth;$('equity').classList.add('flash');}
    prevEquity=eq;
    $('equity').textContent = eq;
    $('disponible').textContent = (+d.balance.available).toFixed(2);
    $('flotante').textContent = money(d.balance.profit_loss);
    $('flotante').className = 'v '+cls(d.balance.profit_loss);
  }
  if(d.precio_gold) $('precio').textContent = d.precio_gold.toFixed(2);
  let ph='';
  if(!d.positions.length) ph='<div class="empty">Sin posiciones — <b>la bóveda espera su momento.</b></div>';
  else{ ph='<table><tr><th></th><th>Dir</th><th>Size</th><th>Entrada</th><th>SL</th><th>TP</th><th>P&L</th></tr>';
    for(const p of d.positions){
      ph+=`<tr><td>${p.epic} ${p.aurex?'':'<span class="tag">manual</span>'}</td>
      <td>${p.dir}</td><td>${p.size}</td><td>${p.entry??'—'}</td>
      <td>${p.sl||'<span class="neg">sin SL</span>'}</td><td>${p.tp||'—'}</td>
      <td class="${cls(p.pnl)}">${money(p.pnl)}</td></tr>`;}
    ph+='</table>';}
  $('positions').innerHTML=ph;
  const t=d.truth;
  $('tpnl').textContent=money(t.total_pnl); $('tpnl').className='v '+cls(t.total_pnl);
  $('wr').textContent=t.wr!=null?t.wr+'%':'—';
  $('pf').textContent=t.pf??'—'; $('ntr').textContent=t.n;
  let ch=''; if(t.closes.length){
    ch='<table><tr><th>Cierre</th><th>P&L · EUR</th></tr>';
    for(const c of t.closes) ch+=`<tr><td>${c.fecha}</td><td class="${cls(c.pnl)}">${money(c.pnl)}</td></tr>`;
    ch+='</table>';}
  $('closes').innerHTML=ch;
  const labels=t.curve.map(x=>x.t), vals=t.curve.map(x=>x.v);
  if(!chart){
    const ctx=$('curve').getContext('2d');
    const g=ctx.createLinearGradient(0,0,0,180);
    g.addColorStop(0,'rgba(212,175,55,.22)'); g.addColorStop(1,'rgba(212,175,55,0)');
    chart=new Chart(ctx,{type:'line',
      data:{labels,datasets:[{data:vals,borderColor:'#d4af37',borderWidth:1.8,
        pointRadius:0,pointHitRadius:12,tension:.25,fill:true,backgroundColor:g}]},
      options:{plugins:{legend:{display:false},tooltip:{
        backgroundColor:'#12100c',borderColor:'#3d3320',borderWidth:1,
        titleColor:'#9c917a',bodyColor:'#f3d878',displayColors:false,
        bodyFont:{family:'IBM Plex Mono'},titleFont:{family:'IBM Plex Mono',size:10}}},
      scales:{x:{grid:{color:'rgba(42,36,25,.5)'},ticks:{color:'#5f584a',maxTicksLimit:8,font:{family:'IBM Plex Mono',size:10}}},
              y:{grid:{color:'rgba(42,36,25,.5)'},ticks:{color:'#5f584a',font:{family:'IBM Plex Mono',size:10}}}}}});
  } else { chart.data.labels=labels; chart.data.datasets[0].data=vals; chart.update('none'); }
  let sh='<table><tr><th>Nivel</th><th>Fecha UTC</th><th>Dir</th><th>Entrada</th><th>Resultado</th><th>P&L est.</th></tr>';
  for(const s of d.signals) sh+=`<tr><td>${s.nivel}</td><td>${s.fecha}</td>
    <td>${s.dir}</td><td>${s.entry}</td><td>${s.resultado}</td><td>${s.pnl}</td></tr>`;
  $('signals').innerHTML=sh+'</table>';
  let mh='<table><tr><th>Monitor</th><th>Última ejecución OK</th><th>Estado</th></tr>';
  const mons=Object.entries(d.monitors);
  if(!mons.length) mh+='<tr><td colspan=3 class="muted">sin registros hoy</td></tr>';
  for(const [k,v] of mons) mh+=`<tr><td>${k}</td><td>${v.last_end}</td>
    <td>${v.ok?'<span class="pos">OK</span>':'<span class="neg">ERROR</span>'}</td></tr>`;
  $('monitors').innerHTML=mh+'</table>';
}
refresh(); setInterval(refresh,30000);
</script></body></html>
"""


@app.route('/')
def index():
    return render_template_string(PAGE)


if __name__ == '__main__':
    print('Aurex Dashboard v1.1 "Boveda" (solo lectura) -> http://localhost:8181')
    app.run(host='127.0.0.1', port=8181, debug=False)
