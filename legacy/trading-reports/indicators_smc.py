"""Indicadores Smart Money Concepts (ICT/SMC)"""
import pandas as pd
import numpy as np

class SmartMoneyConcepts:
    """Implementacion de Smart Money Concepts para intraday"""
    
    @staticmethod
    def detect_order_blocks(df, lookback=20):
        """
        Detecta Order Blocks (zonas institucionales de entrada)
        
        Order Block Alcista: Ultima vela bajista antes de movimiento alcista fuerte
        Order Block Bajista: Ultima vela alcista antes de movimiento bajista fuerte
        """
        order_blocks = []
        
        for i in range(lookback, len(df)):
            # Bullish Order Block
            if (df['close'].iloc[i-1] < df['open'].iloc[i-1] and  # Vela bajista
                df['close'].iloc[i] > df['open'].iloc[i] and      # Vela alcista
                df['close'].iloc[i] > df['high'].iloc[i-1] * 1.005):  # Rompe maximos con fuerza
                
                order_blocks.append({
                    'type': 'BULLISH_OB',
                    'zone_low': df['low'].iloc[i-1],
                    'zone_high': df['high'].iloc[i-1],
                    'index': i-1,
                    'strength': abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['open'].iloc[i]
                })
            
            # Bearish Order Block  
            if (df['close'].iloc[i-1] > df['open'].iloc[i-1] and  # Vela alcista
                df['close'].iloc[i] < df['open'].iloc[i] and      # Vela bajista
                df['close'].iloc[i] < df['low'].iloc[i-1] * 0.995):  # Rompe minimos con fuerza
                
                order_blocks.append({
                    'type': 'BEARISH_OB',
                    'zone_low': df['low'].iloc[i-1],
                    'zone_high': df['high'].iloc[i-1],
                    'index': i-1,
                    'strength': abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['open'].iloc[i]
                })
        
        # Retornar ultimos 5 mas fuertes
        return sorted(order_blocks, key=lambda x: x['strength'], reverse=True)[:5]
    
    @staticmethod
    def detect_fvg(df, min_gap_pct=0.002):
        """
        Fair Value Gaps - Huecos de ineficiencia del mercado
        Ocurren cuando hay un gap entre velas que debe ser rellenado
        """
        fvgs = []
        
        for i in range(2, len(df)):
            # Bullish FVG: gap entre high[i-2] y low[i]
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['close'].iloc[i]
                if gap_size >= min_gap_pct:
                    fvgs.append({
                        'type': 'BULLISH_FVG',
                        'gap_low': df['high'].iloc[i-2],
                        'gap_high': df['low'].iloc[i],
                        'size_pct': gap_size * 100,
                        'index': i
                    })
            
            # Bearish FVG: gap entre low[i-2] y high[i]
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['close'].iloc[i]
                if gap_size >= min_gap_pct:
                    fvgs.append({
                        'type': 'BEARISH_FVG',
                        'gap_low': df['high'].iloc[i],
                        'gap_high': df['low'].iloc[i-2],
                        'size_pct': gap_size * 100,
                        'index': i
                    })
        
        return fvgs[-5:] if fvgs else []
    
    @staticmethod
    def detect_bos_choch(df):
        """
        Break of Structure (BOS) y Change of Character (ChoCh)
        BOS: Ruptura de estructura que confirma tendencia
        ChoCh: Cambio de caracter que indica posible reversa
        """
        signals = []
        highs = []
        lows = []
        
        # Identificar swing highs y lows
        for i in range(5, len(df)-5):
            # Swing High
            if df['high'].iloc[i] == df['high'].iloc[i-5:i+5].max():
                highs.append((i, df['high'].iloc[i]))
            # Swing Low
            if df['low'].iloc[i] == df['low'].iloc[i-5:i+5].min():
                lows.append((i, df['low'].iloc[i]))
        
        # Detectar BOS (Break of Structure)
        if len(highs) >= 2:
            last_high_idx, last_high = highs[-1]
            prev_high_idx, prev_high = highs[-2]
            
            current_price = df['close'].iloc[-1]
            
            # Bullish BOS: precio rompe ultimo high
            if current_price > last_high:
                signals.append({
                    'type': 'BULLISH_BOS',
                    'level': last_high,
                    'strength': (current_price - last_high) / last_high
                })
        
        if len(lows) >= 2:
            last_low_idx, last_low = lows[-1]
            prev_low_idx, prev_low = lows[-2]
            
            current_price = df['close'].iloc[-1]
            
            # Bearish BOS: precio rompe ultimo low
            if current_price < last_low:
                signals.append({
                    'type': 'BEARISH_BOS',
                    'level': last_low,
                    'strength': (last_low - current_price) / last_low
                })
        
        return signals
    
    @staticmethod
    def detect_liquidity_sweep(df):
        """
        Liquidity Sweep - Barrido de liquidez
        Precio toca nivel clave y rechaza rapidamente (stop hunt institucional)
        """
        sweeps = []
        
        for i in range(10, len(df)-1):
            # Alcista: toca minimo reciente y rebota fuerte
            recent_low = df['low'].iloc[i-10:i].min()
            if (df['low'].iloc[i] <= recent_low * 1.001 and  # Toca el minimo
                df['close'].iloc[i] > df['open'].iloc[i] and  # Cierra alcista
                abs(df['close'].iloc[i] - df['low'].iloc[i]) / df['low'].iloc[i] > 0.003):  # Rechazo fuerte
                
                sweeps.append({
                    'type': 'BULLISH_SWEEP',
                    'level': recent_low,
                    'rejection_strength': (df['close'].iloc[i] - df['low'].iloc[i]) / df['low'].iloc[i]
                })
            
            # Bajista: toca maximo reciente y cae fuerte  
            recent_high = df['high'].iloc[i-10:i].max()
            if (df['high'].iloc[i] >= recent_high * 0.999 and  # Toca el maximo
                df['close'].iloc[i] < df['open'].iloc[i] and  # Cierra bajista
                abs(df['high'].iloc[i] - df['close'].iloc[i]) / df['high'].iloc[i] > 0.003):  # Rechazo fuerte
                
                sweeps.append({
                    'type': 'BEARISH_SWEEP',
                    'level': recent_high,
                    'rejection_strength': (df['high'].iloc[i] - df['close'].iloc[i]) / df['high'].iloc[i]
                })
        
        return sweeps[-3:] if sweeps else []
    
    @staticmethod
    def calculate_premium_discount(df):
        """
        Premium/Discount Zones basadas en rango reciente
        Premium = zona cara (arriba del 50% del rango)
        Discount = zona barata (abajo del 50% del rango)
        """
        # Usar ultimas 50 velas para el rango
        lookback = min(50, len(df))
        high = df['high'].iloc[-lookback:].max()
        low = df['low'].iloc[-lookback:].min()
        mid = (high + low) / 2
        
        current = df['close'].iloc[-1]
        
        # Calcular en que zona esta el precio
        range_size = high - low
        position = (current - low) / range_size if range_size > 0 else 0.5
        
        if position > 0.7:
            zone = 'PREMIUM'
        elif position < 0.3:
            zone = 'DISCOUNT'
        else:
            zone = 'EQUILIBRIUM'
        
        return {
            'zone': zone,
            'position_pct': position * 100,
            'high': high,
            'low': low,
            'mid': mid,
            'current': current
        }
    
    @staticmethod
    def analyze_market(df):
        """Analisis completo SMC de un activo"""
        
        results = {
            'order_blocks': SmartMoneyConcepts.detect_order_blocks(df),
            'fvg': SmartMoneyConcepts.detect_fvg(df),
            'bos_choch': SmartMoneyConcepts.detect_bos_choch(df),
            'liquidity_sweeps': SmartMoneyConcepts.detect_liquidity_sweep(df),
            'premium_discount': SmartMoneyConcepts.calculate_premium_discount(df)
        }
        
        return results
