"""
Backtester SMC
==============
Prueba la estrategia contra datos históricos para ver efectividad real.

Autor: Juanpi + Claude
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Optional
import requests
import json

from config import API_KEY, PASSWORD, EMAIL, BASE_URL


@dataclass
class BacktestTrade:
    """Registro de un trade en backtest"""
    entry_time: datetime
    exit_time: datetime
    direction: str  # LONG o SHORT
    entry_price: float
    exit_price: float
    stop_loss: float
    take_profit: float
    result: str  # WIN, LOSS, BREAKEVEN
    pnl_pct: float
    reason: str


class SMCBacktester:
    """Backtester para estrategia SMC"""
    
    def __init__(self):
        self.session = requests.Session()
        self.logged_in = False
        self.trades: List[BacktestTrade] = []
        
    def login(self) -> bool:
        """Conectar a Capital.com"""
        url = f"{BASE_URL}/session"
        headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
        data = {"identifier": EMAIL, "password": PASSWORD}
        
        try:
            r = self.session.post(url, headers=headers, json=data)
            if r.status_code == 200:
                self.session.headers.update({
                    'X-SECURITY-TOKEN': r.headers.get('X-SECURITY-TOKEN'),
                    'CST': r.headers.get('CST'),
                    'Content-Type': 'application/json'
                })
                self.logged_in = True
                return True
        except Exception as e:
            print(f"❌ Error de conexión: {e}")
        return False
    
    def get_historical_data(self, epic: str, resolution: str = "HOUR", max_points: int = 1000) -> Optional[pd.DataFrame]:
        """Obtener datos históricos"""
        if not self.logged_in:
            return None
        
        try:
            r = self.session.get(
                f"{BASE_URL}/prices/{epic}",
                params={'resolution': resolution, 'max': max_points}
            )
            
            if r.status_code == 200:
                data = r.json()
                prices = data.get('prices', [])
                
                df_data = []
                for candle in prices:
                    df_data.append({
                        'timestamp': pd.to_datetime(candle['snapshotTime']),
                        'open': float(candle['openPrice']['bid']),
                        'high': float(candle['highPrice']['bid']),
                        'low': float(candle['lowPrice']['bid']),
                        'close': float(candle['closePrice']['bid']),
                    })
                
                df = pd.DataFrame(df_data)
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
        except Exception as e:
            print(f"❌ Error obteniendo datos: {e}")
        return None
    
    def detect_fvg(self, df: pd.DataFrame, idx: int) -> List[Dict]:
        """Detectar FVGs hasta el índice dado"""
        fvgs = []
        start_idx = max(2, idx - 50)  # Mirar últimas 50 velas
        
        for i in range(start_idx, idx):
            # Bullish FVG
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['close'].iloc[i]
                if gap_size >= 0.002:
                    fvgs.append({
                        'type': 'BULLISH_FVG',
                        'low': df['high'].iloc[i-2],
                        'high': df['low'].iloc[i],
                        'idx': i
                    })
            
            # Bearish FVG
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['close'].iloc[i]
                if gap_size >= 0.002:
                    fvgs.append({
                        'type': 'BEARISH_FVG',
                        'low': df['high'].iloc[i],
                        'high': df['low'].iloc[i-2],
                        'idx': i
                    })
        
        return fvgs[-10:]  # Últimos 10
    
    def detect_order_blocks(self, df: pd.DataFrame, idx: int) -> List[Dict]:
        """Detectar Order Blocks hasta el índice dado"""
        obs = []
        start_idx = max(20, idx - 50)
        
        for i in range(start_idx, idx):
            # Bullish OB
            if (df['close'].iloc[i-1] < df['open'].iloc[i-1] and
                df['close'].iloc[i] > df['open'].iloc[i] and
                df['close'].iloc[i] > df['high'].iloc[i-1] * 1.003):
                obs.append({
                    'type': 'BULLISH_OB',
                    'low': df['low'].iloc[i-1],
                    'high': df['high'].iloc[i-1],
                    'idx': i
                })
            
            # Bearish OB
            if (df['close'].iloc[i-1] > df['open'].iloc[i-1] and
                df['close'].iloc[i] < df['open'].iloc[i] and
                df['close'].iloc[i] < df['low'].iloc[i-1] * 0.997):
                obs.append({
                    'type': 'BEARISH_OB',
                    'low': df['low'].iloc[i-1],
                    'high': df['high'].iloc[i-1],
                    'idx': i
                })
        
        return obs[-5:]
    
    def calculate_rsi(self, df: pd.DataFrame, idx: int, period: int = 14) -> float:
        """Calcular RSI hasta el índice dado"""
        if idx < period + 1:
            return 50
        
        subset = df.iloc[:idx+1]
        delta = subset['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def calculate_atr(self, df: pd.DataFrame, idx: int, period: int = 14) -> float:
        """Calcular ATR hasta el índice dado"""
        if idx < period + 1:
            return df['close'].iloc[idx] * 0.005
        
        subset = df.iloc[:idx+1]
        high = subset['high']
        low = subset['low']
        close = subset['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else df['close'].iloc[idx] * 0.005
    
    def get_premium_discount(self, df: pd.DataFrame, idx: int) -> str:
        """Determinar si está en premium o discount"""
        lookback = min(50, idx)
        subset = df.iloc[idx-lookback:idx+1]
        
        high = subset['high'].max()
        low = subset['low'].min()
        current = df['close'].iloc[idx]
        
        position = (current - low) / (high - low) if (high - low) > 0 else 0.5
        
        if position > 0.7:
            return 'PREMIUM'
        elif position < 0.3:
            return 'DISCOUNT'
        return 'EQUILIBRIUM'
    
    def run_backtest(self, epic: str, start_idx: int = 100) -> Dict:
        """Ejecutar backtest completo"""
        print(f"\n{'='*60}")
        print(f"  BACKTESTING {epic}")
        print(f"{'='*60}\n")
        
        # Obtener datos
        print("📊 Descargando datos históricos...")
        df = self.get_historical_data(epic, "HOUR", 1000)
        
        if df is None or len(df) < start_idx:
            print("❌ No hay suficientes datos")
            return {}
        
        print(f"✅ {len(df)} velas obtenidas")
        print(f"📅 Desde: {df['timestamp'].iloc[0]}")
        print(f"📅 Hasta: {df['timestamp'].iloc[-1]}")
        print(f"\n🔄 Simulando trades...\n")
        
        self.trades = []
        active_zones = []
        in_trade = False
        current_trade = None
        
        # Iterar por cada vela (simulando tiempo real)
        for idx in range(start_idx, len(df)):
            current_price = df['close'].iloc[idx]
            current_time = df['timestamp'].iloc[idx]
            current_high = df['high'].iloc[idx]
            current_low = df['low'].iloc[idx]
            
            # Si hay trade abierto, verificar SL/TP
            if in_trade and current_trade:
                trade_closed = False
                
                if current_trade['direction'] == 'LONG':
                    # Check SL
                    if current_low <= current_trade['sl']:
                        exit_price = current_trade['sl']
                        result = 'LOSS'
                        trade_closed = True
                    # Check TP
                    elif current_high >= current_trade['tp']:
                        exit_price = current_trade['tp']
                        result = 'WIN'
                        trade_closed = True
                else:  # SHORT
                    # Check SL
                    if current_high >= current_trade['sl']:
                        exit_price = current_trade['sl']
                        result = 'LOSS'
                        trade_closed = True
                    # Check TP
                    elif current_low <= current_trade['tp']:
                        exit_price = current_trade['tp']
                        result = 'WIN'
                        trade_closed = True
                
                if trade_closed:
                    pnl_pct = ((exit_price - current_trade['entry']) / current_trade['entry']) * 100
                    if current_trade['direction'] == 'SHORT':
                        pnl_pct = -pnl_pct
                    
                    trade = BacktestTrade(
                        entry_time=current_trade['entry_time'],
                        exit_time=current_time,
                        direction=current_trade['direction'],
                        entry_price=current_trade['entry'],
                        exit_price=exit_price,
                        stop_loss=current_trade['sl'],
                        take_profit=current_trade['tp'],
                        result=result,
                        pnl_pct=pnl_pct,
                        reason=current_trade['reason']
                    )
                    self.trades.append(trade)
                    
                    emoji = "✅" if result == 'WIN' else "❌"
                    print(f"{emoji} {current_time.strftime('%Y-%m-%d %H:%M')} | {current_trade['direction']} | Entry: {current_trade['entry']:.2f} | Exit: {exit_price:.2f} | {result} ({pnl_pct:+.2f}%)")
                    
                    in_trade = False
                    current_trade = None
                    continue
            
            # Si no hay trade, buscar oportunidades
            if not in_trade:
                # Detectar zonas SMC
                fvgs = self.detect_fvg(df, idx)
                obs = self.detect_order_blocks(df, idx)
                rsi = self.calculate_rsi(df, idx)
                atr = self.calculate_atr(df, idx)
                pd_zone = self.get_premium_discount(df, idx)
                
                # Buscar entrada en FVGs
                for fvg in fvgs:
                    # Solo FVGs recientes (últimas 20 velas)
                    if idx - fvg['idx'] > 20:
                        continue
                    
                    # LONG: precio entra en Bullish FVG
                    if fvg['type'] == 'BULLISH_FVG':
                        if fvg['low'] <= current_low <= fvg['high']:
                            # Confirmaciones
                            confirmations = 1  # FVG
                            reasons = ['Bullish FVG']
                            
                            if rsi < 40:
                                confirmations += 1
                                reasons.append(f'RSI {rsi:.0f}')
                            if pd_zone == 'DISCOUNT':
                                confirmations += 1
                                reasons.append('Discount')
                            
                            if confirmations >= 2:
                                entry = current_price
                                sl = fvg['low'] - (atr * 1.5)
                                tp = entry + (atr * 2)
                                
                                current_trade = {
                                    'direction': 'LONG',
                                    'entry': entry,
                                    'entry_time': current_time,
                                    'sl': sl,
                                    'tp': tp,
                                    'reason': ', '.join(reasons)
                                }
                                in_trade = True
                                print(f"🟢 {current_time.strftime('%Y-%m-%d %H:%M')} | LONG @ {entry:.2f} | SL: {sl:.2f} | TP: {tp:.2f} | {', '.join(reasons)}")
                                break
                    
                    # SHORT: precio entra en Bearish FVG
                    elif fvg['type'] == 'BEARISH_FVG':
                        if fvg['low'] <= current_high <= fvg['high']:
                            confirmations = 1
                            reasons = ['Bearish FVG']
                            
                            if rsi > 60:
                                confirmations += 1
                                reasons.append(f'RSI {rsi:.0f}')
                            if pd_zone == 'PREMIUM':
                                confirmations += 1
                                reasons.append('Premium')
                            
                            if confirmations >= 2:
                                entry = current_price
                                sl = fvg['high'] + (atr * 1.5)
                                tp = entry - (atr * 2)
                                
                                current_trade = {
                                    'direction': 'SHORT',
                                    'entry': entry,
                                    'entry_time': current_time,
                                    'sl': sl,
                                    'tp': tp,
                                    'reason': ', '.join(reasons)
                                }
                                in_trade = True
                                print(f"🔴 {current_time.strftime('%Y-%m-%d %H:%M')} | SHORT @ {entry:.2f} | SL: {sl:.2f} | TP: {tp:.2f} | {', '.join(reasons)}")
                                break
        
        # Calcular estadísticas
        return self.calculate_stats()
    
    def calculate_stats(self) -> Dict:
        """Calcular estadísticas del backtest"""
        if not self.trades:
            print("\n⚠️ No se ejecutaron trades en el periodo")
            return {}
        
        total = len(self.trades)
        wins = len([t for t in self.trades if t.result == 'WIN'])
        losses = len([t for t in self.trades if t.result == 'LOSS'])
        
        win_rate = (wins / total) * 100 if total > 0 else 0
        
        total_pnl = sum(t.pnl_pct for t in self.trades)
        avg_win = np.mean([t.pnl_pct for t in self.trades if t.result == 'WIN']) if wins > 0 else 0
        avg_loss = np.mean([t.pnl_pct for t in self.trades if t.result == 'LOSS']) if losses > 0 else 0
        
        # Profit factor
        gross_profit = sum(t.pnl_pct for t in self.trades if t.pnl_pct > 0)
        gross_loss = abs(sum(t.pnl_pct for t in self.trades if t.pnl_pct < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Max drawdown
        cumulative = []
        running = 0
        for t in self.trades:
            running += t.pnl_pct
            cumulative.append(running)
        
        peak = cumulative[0]
        max_dd = 0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        
        stats = {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_pnl_pct': total_pnl,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_dd
        }
        
        # Imprimir resumen
        print(f"\n{'='*60}")
        print(f"  📊 RESULTADOS DEL BACKTEST")
        print(f"{'='*60}")
        print(f"""
  Total trades:     {total}
  Ganados:          {wins} ({win_rate:.1f}%)
  Perdidos:         {losses} ({100-win_rate:.1f}%)
  
  PnL Total:        {total_pnl:+.2f}%
  Ganancia media:   {avg_win:+.2f}%
  Pérdida media:    {avg_loss:.2f}%
  
  Profit Factor:    {profit_factor:.2f}
  Max Drawdown:     {max_dd:.2f}%
""")
        
        # Evaluación
        print(f"{'='*60}")
        print(f"  🎯 EVALUACIÓN")
        print(f"{'='*60}")
        
        if win_rate >= 50 and profit_factor >= 1.5:
            print("  ✅ Estrategia RENTABLE - OK para usar")
        elif win_rate >= 45 and profit_factor >= 1.2:
            print("  ⚠️ Estrategia MARGINAL - Usar con precaución")
        else:
            print("  ❌ Estrategia NO RENTABLE - Necesita mejoras")
        
        print(f"{'='*60}\n")
        
        return stats


def main():
    """Ejecutar backtest"""
    backtester = SMCBacktester()
    
    print("\n🔐 Conectando a Capital.com...")
    if not backtester.login():
        print("❌ No se pudo conectar")
        return
    print("✅ Conectado\n")
    
    # Backtest GOLD
    gold_stats = backtester.run_backtest("GOLD")
    
    # Backtest US30
    us30_stats = backtester.run_backtest("US30")
    
    # Guardar resultados
    results = {
        'timestamp': datetime.now().isoformat(),
        'GOLD': gold_stats,
        'US30': us30_stats
    }
    
    with open('backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("💾 Resultados guardados en backtest_results.json")


if __name__ == '__main__':
    main()
