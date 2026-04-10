"""
Generador de Informes para Análisis por IA
==========================================
Genera informes exhaustivos de activos para ser analizados por Claude.
En lugar de generar señales, extrae TODA la información relevante.
"""
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

from config import *
from indicators_smc import SmartMoneyConcepts


@dataclass
class MarketContext:
    """Contexto general del mercado"""
    current_price: float
    daily_change_pct: float
    weekly_change_pct: float
    monthly_change_pct: float
    distance_from_daily_high_pct: float
    distance_from_daily_low_pct: float
    distance_from_weekly_high_pct: float
    distance_from_weekly_low_pct: float
    atr_14: float
    atr_pct: float  # ATR como % del precio
    volatility_state: str  # LOW, NORMAL, HIGH, EXTREME


@dataclass 
class PriceLevel:
    """Nivel de precio significativo"""
    price: float
    type: str  # RESISTANCE, SUPPORT, PIVOT, ORDER_BLOCK, FVG
    strength: str  # WEAK, MODERATE, STRONG
    touches: int
    last_test: str  # timestamp
    notes: str


class CapitalAPI:
    """Cliente API para Capital.com"""
    
    def __init__(self):
        self.session = requests.Session()
        self.cst = None
        self.token = None
        self.logged_in = False
        
    def login(self) -> bool:
        """Autenticar con Capital.com"""
        url = f"{BASE_URL}/session"
        headers = {"X-CAP-API-KEY": API_KEY, "Content-Type": "application/json"}
        data = {"identifier": EMAIL, "password": PASSWORD}
        
        try:
            r = self.session.post(url, headers=headers, json=data)
            if r.status_code == 200:
                self.cst = r.headers.get('CST')
                self.token = r.headers.get('X-SECURITY-TOKEN')
                self.session.headers.update({
                    'X-SECURITY-TOKEN': self.token,
                    'CST': self.cst,
                    'Content-Type': 'application/json'
                })
                self.logged_in = True
                return True
        except Exception as e:
            print(f"Error de conexión: {e}")
        return False
    
    def get_prices(self, epic: str, resolution: str = "HOUR", max_points: int = 200) -> Optional[pd.DataFrame]:
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
                        'timestamp': candle['snapshotTime'],
                        'open': float(candle['openPrice']['bid']),
                        'high': float(candle['highPrice']['bid']),
                        'low': float(candle['lowPrice']['bid']),
                        'close': float(candle['closePrice']['bid']),
                        'volume': float(candle.get('lastTradedVolume', 0))
                    })
                
                df = pd.DataFrame(df_data)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp').reset_index(drop=True)
                return df
                
        except Exception as e:
            print(f"Error obteniendo precios: {e}")
        return None
    
    def get_market_info(self, epic: str) -> Optional[Dict]:
        """Obtener información del mercado"""
        if not self.logged_in:
            return None
            
        try:
            r = self.session.get(f"{BASE_URL}/markets/{epic}")
            if r.status_code == 200:
                return r.json()
        except:
            pass
        return None


class TechnicalAnalyzer:
    """Análisis técnico extendido"""
    
    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return round(atr, 5)
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """Relative Strength Index"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return round(rsi.iloc[-1], 2)
    
    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int) -> float:
        """Exponential Moving Average"""
        return round(df['close'].ewm(span=period, adjust=False).mean().iloc[-1], 5)
    
    @staticmethod
    def calculate_sma(df: pd.DataFrame, period: int) -> float:
        """Simple Moving Average"""
        return round(df['close'].rolling(window=period).mean().iloc[-1], 5)
    
    @staticmethod
    def calculate_bollinger_bands(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> Dict:
        """Bandas de Bollinger"""
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        current_price = df['close'].iloc[-1]
        bb_position = (current_price - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])
        
        return {
            'upper': round(upper.iloc[-1], 5),
            'middle': round(sma.iloc[-1], 5),
            'lower': round(lower.iloc[-1], 5),
            'bandwidth': round((upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1] * 100, 2),
            'position_pct': round(bb_position * 100, 2)
        }
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame) -> Dict:
        """MACD"""
        ema12 = df['close'].ewm(span=12, adjust=False).mean()
        ema26 = df['close'].ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': round(macd_line.iloc[-1], 5),
            'signal': round(signal_line.iloc[-1], 5),
            'histogram': round(histogram.iloc[-1], 5),
            'trend': 'BULLISH' if macd_line.iloc[-1] > signal_line.iloc[-1] else 'BEARISH',
            'histogram_increasing': histogram.iloc[-1] > histogram.iloc[-2]
        }
    
    @staticmethod
    def find_support_resistance(df: pd.DataFrame, lookback: int = 50) -> List[PriceLevel]:
        """Encontrar niveles de soporte y resistencia"""
        levels = []
        subset = df.tail(lookback)
        
        # Encontrar swing highs y lows
        for i in range(5, len(subset) - 5):
            # Swing High (resistencia)
            if subset['high'].iloc[i] == subset['high'].iloc[i-5:i+5].max():
                price = subset['high'].iloc[i]
                # Contar toques
                touches = len(subset[abs(subset['high'] - price) / price < 0.002])
                
                levels.append(PriceLevel(
                    price=round(price, 5),
                    type='RESISTANCE',
                    strength='STRONG' if touches >= 3 else 'MODERATE' if touches >= 2 else 'WEAK',
                    touches=touches,
                    last_test=str(subset['timestamp'].iloc[i]),
                    notes=f"Swing high con {touches} toques"
                ))
            
            # Swing Low (soporte)
            if subset['low'].iloc[i] == subset['low'].iloc[i-5:i+5].min():
                price = subset['low'].iloc[i]
                touches = len(subset[abs(subset['low'] - price) / price < 0.002])
                
                levels.append(PriceLevel(
                    price=round(price, 5),
                    type='SUPPORT',
                    strength='STRONG' if touches >= 3 else 'MODERATE' if touches >= 2 else 'WEAK',
                    touches=touches,
                    last_test=str(subset['timestamp'].iloc[i]),
                    notes=f"Swing low con {touches} toques"
                ))
        
        # Eliminar duplicados cercanos y ordenar por precio
        unique_levels = []
        for level in sorted(levels, key=lambda x: x.price):
            if not unique_levels or abs(level.price - unique_levels[-1].price) / level.price > 0.003:
                unique_levels.append(level)
        
        return unique_levels
    
    @staticmethod
    def calculate_pivot_points(df: pd.DataFrame) -> Dict:
        """Pivot Points (Classic)"""
        # Usar última vela completada
        high = df['high'].iloc[-2]
        low = df['low'].iloc[-2]
        close = df['close'].iloc[-2]
        
        pivot = (high + low + close) / 3
        
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        r2 = pivot + (high - low)
        s2 = pivot - (high - low)
        r3 = high + 2 * (pivot - low)
        s3 = low - 2 * (high - pivot)
        
        return {
            'pivot': round(pivot, 5),
            'r1': round(r1, 5),
            'r2': round(r2, 5),
            'r3': round(r3, 5),
            's1': round(s1, 5),
            's2': round(s2, 5),
            's3': round(s3, 5)
        }
    
    @staticmethod
    def get_candle_patterns(df: pd.DataFrame) -> List[Dict]:
        """Detectar patrones de velas recientes"""
        patterns = []
        
        for i in range(-3, 0):  # Últimas 3 velas
            o, h, l, c = df['open'].iloc[i], df['high'].iloc[i], df['low'].iloc[i], df['close'].iloc[i]
            body = abs(c - o)
            range_size = h - l
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l
            
            pattern = None
            
            # Doji
            if body < range_size * 0.1:
                pattern = 'DOJI'
            # Hammer / Hanging Man
            elif lower_wick > body * 2 and upper_wick < body * 0.5:
                pattern = 'HAMMER' if c > o else 'HANGING_MAN'
            # Shooting Star / Inverted Hammer
            elif upper_wick > body * 2 and lower_wick < body * 0.5:
                pattern = 'SHOOTING_STAR' if c < o else 'INVERTED_HAMMER'
            # Marubozu
            elif body > range_size * 0.9:
                pattern = 'BULLISH_MARUBOZU' if c > o else 'BEARISH_MARUBOZU'
            # Engulfing (necesita vela anterior)
            elif i > -3:
                prev_o, prev_c = df['open'].iloc[i-1], df['close'].iloc[i-1]
                if c > o and prev_c < prev_o and c > prev_o and o < prev_c:
                    pattern = 'BULLISH_ENGULFING'
                elif c < o and prev_c > prev_o and c < prev_o and o > prev_c:
                    pattern = 'BEARISH_ENGULFING'
            
            if pattern:
                patterns.append({
                    'pattern': pattern,
                    'candle_index': i,
                    'timestamp': str(df['timestamp'].iloc[i]),
                    'body_size': round(body, 5),
                    'range_size': round(range_size, 5)
                })
        
        return patterns


class ReportGenerator:
    """Generador principal de informes"""
    
    def __init__(self):
        self.api = CapitalAPI()
        self.smc = SmartMoneyConcepts()
        self.ta = TechnicalAnalyzer()
        
    def generate_report(self, epic: str) -> Optional[Dict]:
        """Generar informe completo de un activo"""
        
        print(f"  Obteniendo datos de {epic}...")
        
        # Obtener datos en múltiples timeframes
        df_h1 = self.api.get_prices(epic, "HOUR", 200)
        df_h4 = self.api.get_prices(epic, "HOUR_4", 100)
        df_d1 = self.api.get_prices(epic, "DAY", 60)
        
        if df_h1 is None or len(df_h1) < 50:
            print(f"  No hay suficientes datos para {epic}")
            return None
        
        # Información del mercado
        market_info = self.api.get_market_info(epic)
        
        current_price = df_h1['close'].iloc[-1]
        
        # ==========================================
        # CONSTRUIR INFORME COMPLETO
        # ==========================================
        
        report = {
            'metadata': {
                'epic': epic,
                'generated_at': datetime.now().isoformat(),
                'current_price': round(current_price, 5),
                'market_status': market_info.get('marketStatus', 'UNKNOWN') if market_info else 'UNKNOWN'
            },
            
            'price_action': self._analyze_price_action(df_h1, df_h4, df_d1),
            
            'technical_indicators': {
                'h1': self._get_indicators(df_h1),
                'h4': self._get_indicators(df_h4) if df_h4 is not None else None,
                'd1': self._get_indicators(df_d1) if df_d1 is not None else None
            },
            
            'smc_analysis': {
                'h1': self._get_smc_analysis(df_h1),
                'h4': self._get_smc_analysis(df_h4) if df_h4 is not None else None
            },
            
            'key_levels': self._get_key_levels(df_h1, df_d1),
            
            'candle_patterns': self.ta.get_candle_patterns(df_h1),
            
            'volatility': self._analyze_volatility(df_h1, df_d1),
            
            'raw_data': {
                'last_20_candles_h1': self._format_candles(df_h1.tail(20)),
                'last_10_candles_h4': self._format_candles(df_h4.tail(10)) if df_h4 is not None else None,
                'last_5_candles_d1': self._format_candles(df_d1.tail(5)) if df_d1 is not None else None
            }
        }
        
        return report
    
    def _analyze_price_action(self, df_h1: pd.DataFrame, df_h4: pd.DataFrame, df_d1: pd.DataFrame) -> Dict:
        """Analizar acción del precio"""
        current = df_h1['close'].iloc[-1]
        
        # Cambios porcentuales
        daily_change = (current - df_h1['open'].iloc[-24]) / df_h1['open'].iloc[-24] * 100 if len(df_h1) >= 24 else 0
        weekly_change = (current - df_h1['open'].iloc[-120]) / df_h1['open'].iloc[-120] * 100 if len(df_h1) >= 120 else 0
        
        # Rangos
        daily_high = df_h1['high'].iloc[-24:].max() if len(df_h1) >= 24 else df_h1['high'].max()
        daily_low = df_h1['low'].iloc[-24:].min() if len(df_h1) >= 24 else df_h1['low'].min()
        weekly_high = df_h1['high'].iloc[-120:].max() if len(df_h1) >= 120 else df_h1['high'].max()
        weekly_low = df_h1['low'].iloc[-120:].min() if len(df_h1) >= 120 else df_h1['low'].min()
        
        # Tendencia
        ema_20 = df_h1['close'].ewm(span=20).mean().iloc[-1]
        ema_50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
        
        if current > ema_20 > ema_50:
            trend = 'BULLISH'
        elif current < ema_20 < ema_50:
            trend = 'BEARISH'
        else:
            trend = 'RANGING'
        
        return {
            'current_price': round(current, 5),
            'daily_change_pct': round(daily_change, 2),
            'weekly_change_pct': round(weekly_change, 2),
            'daily_high': round(daily_high, 5),
            'daily_low': round(daily_low, 5),
            'daily_range': round(daily_high - daily_low, 5),
            'weekly_high': round(weekly_high, 5),
            'weekly_low': round(weekly_low, 5),
            'weekly_range': round(weekly_high - weekly_low, 5),
            'position_in_daily_range_pct': round((current - daily_low) / (daily_high - daily_low) * 100, 2) if daily_high != daily_low else 50,
            'position_in_weekly_range_pct': round((current - weekly_low) / (weekly_high - weekly_low) * 100, 2) if weekly_high != weekly_low else 50,
            'trend_h1': trend,
            'above_ema_20': current > ema_20,
            'above_ema_50': current > ema_50,
            'ema_20': round(ema_20, 5),
            'ema_50': round(ema_50, 5)
        }
    
    def _get_indicators(self, df: pd.DataFrame) -> Dict:
        """Obtener todos los indicadores técnicos"""
        if df is None or len(df) < 30:
            return None
            
        return {
            'rsi_14': self.ta.calculate_rsi(df, 14),
            'rsi_state': 'OVERBOUGHT' if self.ta.calculate_rsi(df, 14) > 70 else 'OVERSOLD' if self.ta.calculate_rsi(df, 14) < 30 else 'NEUTRAL',
            'macd': self.ta.calculate_macd(df),
            'bollinger': self.ta.calculate_bollinger_bands(df),
            'ema_9': self.ta.calculate_ema(df, 9),
            'ema_21': self.ta.calculate_ema(df, 21),
            'ema_50': self.ta.calculate_ema(df, 50),
            'ema_200': self.ta.calculate_ema(df, 200) if len(df) >= 200 else None,
            'sma_20': self.ta.calculate_sma(df, 20),
            'sma_50': self.ta.calculate_sma(df, 50),
            'atr_14': self.ta.calculate_atr(df, 14),
            'pivot_points': self.ta.calculate_pivot_points(df)
        }
    
    def _get_smc_analysis(self, df: pd.DataFrame) -> Dict:
        """Análisis SMC completo"""
        if df is None or len(df) < 30:
            return None
            
        smc_data = self.smc.analyze_market(df)
        
        return {
            'order_blocks': [
                {
                    'type': ob['type'],
                    'zone_low': round(ob['zone_low'], 5),
                    'zone_high': round(ob['zone_high'], 5),
                    'strength': round(ob['strength'] * 100, 2)
                }
                for ob in smc_data['order_blocks']
            ],
            'fair_value_gaps': [
                {
                    'type': fvg['type'],
                    'gap_low': round(fvg['gap_low'], 5),
                    'gap_high': round(fvg['gap_high'], 5),
                    'size_pct': round(fvg['size_pct'], 3)
                }
                for fvg in smc_data['fvg']
            ],
            'break_of_structure': [
                {
                    'type': bos['type'],
                    'level': round(bos['level'], 5),
                    'strength_pct': round(bos['strength'] * 100, 3)
                }
                for bos in smc_data['bos_choch']
            ],
            'liquidity_sweeps': [
                {
                    'type': sweep['type'],
                    'level': round(sweep['level'], 5),
                    'rejection_strength_pct': round(sweep['rejection_strength'] * 100, 3)
                }
                for sweep in smc_data['liquidity_sweeps']
            ],
            'premium_discount': smc_data['premium_discount']
        }
    
    def _get_key_levels(self, df_h1: pd.DataFrame, df_d1: pd.DataFrame) -> Dict:
        """Obtener niveles clave"""
        levels_h1 = self.ta.find_support_resistance(df_h1, 100)
        levels_d1 = self.ta.find_support_resistance(df_d1, 30) if df_d1 is not None else []
        
        current = df_h1['close'].iloc[-1]
        
        # Separar por tipo y cercanía
        resistances = sorted([l for l in levels_h1 + levels_d1 if l.price > current], key=lambda x: x.price)[:5]
        supports = sorted([l for l in levels_h1 + levels_d1 if l.price < current], key=lambda x: x.price, reverse=True)[:5]
        
        return {
            'nearest_resistance': asdict(resistances[0]) if resistances else None,
            'nearest_support': asdict(supports[0]) if supports else None,
            'all_resistances': [asdict(r) for r in resistances],
            'all_supports': [asdict(s) for s in supports],
            'pivot_points': self.ta.calculate_pivot_points(df_h1)
        }
    
    def _analyze_volatility(self, df_h1: pd.DataFrame, df_d1: pd.DataFrame) -> Dict:
        """Analizar volatilidad"""
        atr_h1 = self.ta.calculate_atr(df_h1, 14)
        atr_d1 = self.ta.calculate_atr(df_d1, 14) if df_d1 is not None else None
        
        current = df_h1['close'].iloc[-1]
        atr_pct = (atr_h1 / current) * 100
        
        # Comparar ATR actual vs promedio
        atr_series = []
        for i in range(14, len(df_h1)):
            subset = df_h1.iloc[:i+1]
            atr_series.append(self.ta.calculate_atr(subset, 14))
        
        avg_atr = np.mean(atr_series[-50:]) if len(atr_series) >= 50 else np.mean(atr_series)
        
        if atr_h1 > avg_atr * 1.5:
            state = 'HIGH'
        elif atr_h1 < avg_atr * 0.5:
            state = 'LOW'
        else:
            state = 'NORMAL'
        
        return {
            'atr_h1': round(atr_h1, 5),
            'atr_h1_pct': round(atr_pct, 3),
            'atr_d1': round(atr_d1, 5) if atr_d1 else None,
            'average_atr_h1': round(avg_atr, 5),
            'volatility_state': state,
            'atr_vs_average_ratio': round(atr_h1 / avg_atr, 2) if avg_atr > 0 else 1
        }
    
    def _format_candles(self, df: pd.DataFrame) -> List[Dict]:
        """Formatear velas para el informe"""
        candles = []
        for _, row in df.iterrows():
            candles.append({
                'timestamp': str(row['timestamp']),
                'open': round(row['open'], 5),
                'high': round(row['high'], 5),
                'low': round(row['low'], 5),
                'close': round(row['close'], 5),
                'volume': row.get('volume', 0),
                'body_type': 'BULLISH' if row['close'] > row['open'] else 'BEARISH' if row['close'] < row['open'] else 'DOJI'
            })
        return candles
    
    def run(self, assets: List[str] = None) -> Dict:
        """Ejecutar generación de informes"""
        if assets is None:
            assets = ASSETS
        
        print("=" * 80)
        print(f"GENERADOR DE INFORMES PARA IA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Login
        print("\nAutenticando con Capital.com...")
        if not self.api.login():
            print("Error de autenticacion")
            return None
        print("Conectado\n")

        # Generar informes
        reports = {}
        for epic in assets:
            print(f"\nProcesando {epic}...")
            report = self.generate_report(epic)
            if report:
                reports[epic] = report
                print(f"  Informe generado para {epic}")
            else:
                print(f"  No se pudo generar informe para {epic}")
        
        # Compilar resultado final
        output = {
            'generated_at': datetime.now().isoformat(),
            'assets_analyzed': len(reports),
            'reports': reports
        }
        
        # Guardar JSON
        self._save_report(output)
        
        # Guardar Markdown (más legible para el chat)
        self._save_markdown(output)
        
        return output
    
    def _save_report(self, output: Dict):
        """Guardar informe en JSON"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")

        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        json_path = reports_dir / f"{timestamp}_analysis.json"

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nJSON guardado: {json_path}")

    def _save_markdown(self, output: Dict):
        """Guardar informe en Markdown (ideal para pasar a Claude)"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%Hh%M")
        reports_dir = Path(__file__).parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        md_path = reports_dir / f"{timestamp}_analysis.md"
        
        md_content = f"""# Informe de Análisis de Mercados
**Generado:** {output['generated_at']}
**Activos analizados:** {output['assets_analyzed']}

---

"""
        for epic, report in output['reports'].items():
            pa = report['price_action']
            vol = report['volatility']
            kl = report['key_levels']
            
            md_content += f"""## {epic}
**Precio actual:** {report['metadata']['current_price']}
**Estado del mercado:** {report['metadata']['market_status']}

### Acción del Precio
- Cambio diario: {pa['daily_change_pct']}%
- Cambio semanal: {pa['weekly_change_pct']}%
- Tendencia H1: {pa['trend_h1']}
- Posición en rango diario: {pa['position_in_daily_range_pct']}%
- Rango diario: {pa['daily_low']} - {pa['daily_high']}

### Volatilidad
- ATR (H1): {vol['atr_h1']} ({vol['atr_h1_pct']}%)
- Estado: {vol['volatility_state']}
- ATR vs promedio: {vol['atr_vs_average_ratio']}x

### Indicadores Técnicos (H1)
"""
            if report['technical_indicators']['h1']:
                ti = report['technical_indicators']['h1']
                md_content += f"""- RSI(14): {ti['rsi_14']} ({ti['rsi_state']})
- MACD: {ti['macd']['trend']} (histograma: {ti['macd']['histogram']})
- Bollinger: {ti['bollinger']['position_pct']}% del rango
- EMA 9/21/50: {ti['ema_9']} / {ti['ema_21']} / {ti['ema_50']}

"""

            md_content += f"""### Análisis SMC (H1)
"""
            if report['smc_analysis']['h1']:
                smc = report['smc_analysis']['h1']
                md_content += f"""- Zona Premium/Discount: {smc['premium_discount']['zone']} ({smc['premium_discount']['position_pct']:.1f}%)
- Order Blocks: {len(smc['order_blocks'])} detectados
- Fair Value Gaps: {len(smc['fair_value_gaps'])} detectados
- Break of Structure: {len(smc['break_of_structure'])} señales
- Liquidity Sweeps: {len(smc['liquidity_sweeps'])} detectados

"""
                
                # Detallar OBs y FVGs
                for ob in smc['order_blocks'][:3]:
                    md_content += f"  - {ob['type']}: {ob['zone_low']} - {ob['zone_high']} (fuerza: {ob['strength']}%)\n"
                for fvg in smc['fair_value_gaps'][:3]:
                    md_content += f"  - {fvg['type']}: {fvg['gap_low']} - {fvg['gap_high']} ({fvg['size_pct']:.2f}%)\n"

            md_content += f"""
### Niveles Clave
"""
            if kl['nearest_resistance']:
                md_content += f"- Resistencia más cercana: {kl['nearest_resistance']['price']} ({kl['nearest_resistance']['strength']})\n"
            if kl['nearest_support']:
                md_content += f"- Soporte más cercano: {kl['nearest_support']['price']} ({kl['nearest_support']['strength']})\n"
            
            pp = kl['pivot_points']
            md_content += f"""- Pivote: {pp['pivot']}
- R1/R2/R3: {pp['r1']} / {pp['r2']} / {pp['r3']}
- S1/S2/S3: {pp['s1']} / {pp['s2']} / {pp['s3']}

### Patrones de Velas Recientes
"""
            for pattern in report['candle_patterns']:
                md_content += f"- {pattern['pattern']} en {pattern['timestamp']}\n"
            
            md_content += f"""
### Datos Crudos (Últimas 5 velas H1)
| Timestamp | Open | High | Low | Close | Tipo |
|-----------|------|------|-----|-------|------|
"""
            for candle in report['raw_data']['last_20_candles_h1'][-5:]:
                md_content += f"| {candle['timestamp'][:16]} | {candle['open']} | {candle['high']} | {candle['low']} | {candle['close']} | {candle['body_type']} |\n"
            
            md_content += "\n---\n\n"
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"Markdown guardado: {md_path}")


if __name__ == '__main__':
    generator = ReportGenerator()
    generator.run()  # Sin parámetros, usará ASSETS de config.py
