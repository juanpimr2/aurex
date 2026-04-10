"""
Auto-Trader SMC con Alertas en Consola
======================================
Monitorea precios en tiempo real y ejecuta trades
cuando se cumplen condiciones SMC.

Autor: Juanpi + Claude
Versión: 1.0
"""
import json
import asyncio
import websockets
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum
import threading
import time

# Importar configuración
from config import API_KEY, PASSWORD, EMAIL, BASE_URL


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    NONE = "NONE"


@dataclass
class TradingSignal:
    """Señal de trading generada"""
    epic: str
    signal_type: SignalType
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    reason: str
    confidence: float  # 0-100
    timestamp: datetime


@dataclass
class AlertZone:
    """Zona de alerta para un activo"""
    epic: str
    zone_type: str  # DEMAND, SUPPLY, FVG
    price_low: float
    price_high: float
    direction: str  # LONG, SHORT
    active: bool = True


class ConsoleAlert:
    """Sistema de alertas por consola con colores"""
    
    COLORS = {
        'RED': '\033[91m',
        'GREEN': '\033[92m',
        'YELLOW': '\033[93m',
        'BLUE': '\033[94m',
        'MAGENTA': '\033[95m',
        'CYAN': '\033[96m',
        'WHITE': '\033[97m',
        'BOLD': '\033[1m',
        'END': '\033[0m'
    }
    
    @staticmethod
    def print_banner():
        """Imprime banner de inicio"""
        print(f"""
{ConsoleAlert.COLORS['CYAN']}╔══════════════════════════════════════════════════════════════╗
║  {ConsoleAlert.COLORS['BOLD']}🤖 AUTO-TRADER SMC v1.0{ConsoleAlert.COLORS['END']}{ConsoleAlert.COLORS['CYAN']}                                      ║
║  Sistema de Trading Automático con Smart Money Concepts       ║
╚══════════════════════════════════════════════════════════════╝{ConsoleAlert.COLORS['END']}
""")
    
    @staticmethod
    def info(message: str):
        """Mensaje informativo"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{ConsoleAlert.COLORS['BLUE']}[{timestamp}] ℹ️  {message}{ConsoleAlert.COLORS['END']}")
    
    @staticmethod
    def success(message: str):
        """Mensaje de éxito"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{ConsoleAlert.COLORS['GREEN']}[{timestamp}] ✅ {message}{ConsoleAlert.COLORS['END']}")
    
    @staticmethod
    def warning(message: str):
        """Mensaje de advertencia"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{ConsoleAlert.COLORS['YELLOW']}[{timestamp}] ⚠️  {message}{ConsoleAlert.COLORS['END']}")
    
    @staticmethod
    def error(message: str):
        """Mensaje de error"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"{ConsoleAlert.COLORS['RED']}[{timestamp}] ❌ {message}{ConsoleAlert.COLORS['END']}")
    
    @staticmethod
    def trade_alert(signal: TradingSignal):
        """Alerta de trade con formato especial"""
        color = ConsoleAlert.COLORS['GREEN'] if signal.signal_type == SignalType.LONG else ConsoleAlert.COLORS['RED']
        direction = "🟢 LONG" if signal.signal_type == SignalType.LONG else "🔴 SHORT"
        
        print(f"""
{ConsoleAlert.COLORS['BOLD']}╔══════════════════════════════════════════════════════════════╗
║  {color}🚨 SEÑAL DE TRADING DETECTADA{ConsoleAlert.COLORS['END']}{ConsoleAlert.COLORS['BOLD']}                               ║
╠══════════════════════════════════════════════════════════════╣{ConsoleAlert.COLORS['END']}
║  {ConsoleAlert.COLORS['CYAN']}Activo:{ConsoleAlert.COLORS['END']} {signal.epic:<15} {ConsoleAlert.COLORS['CYAN']}Dirección:{ConsoleAlert.COLORS['END']} {direction}
║  {ConsoleAlert.COLORS['CYAN']}Entry:{ConsoleAlert.COLORS['END']}  {signal.entry_price:<15.5f} {ConsoleAlert.COLORS['CYAN']}Confianza:{ConsoleAlert.COLORS['END']} {signal.confidence:.0f}%
║  {ConsoleAlert.COLORS['RED']}SL:{ConsoleAlert.COLORS['END']}     {signal.stop_loss:<15.5f}
║  {ConsoleAlert.COLORS['GREEN']}TP1:{ConsoleAlert.COLORS['END']}    {signal.take_profit_1:<15.5f}
║  {ConsoleAlert.COLORS['GREEN']}TP2:{ConsoleAlert.COLORS['END']}    {signal.take_profit_2:<15.5f}
║  {ConsoleAlert.COLORS['YELLOW']}Razón:{ConsoleAlert.COLORS['END']} {signal.reason[:50]}
{ConsoleAlert.COLORS['BOLD']}╚══════════════════════════════════════════════════════════════╝{ConsoleAlert.COLORS['END']}
""")
    
    @staticmethod
    def price_update(epic: str, bid: float, ask: float, change_pct: float):
        """Actualización de precio"""
        color = ConsoleAlert.COLORS['GREEN'] if change_pct >= 0 else ConsoleAlert.COLORS['RED']
        arrow = "↑" if change_pct >= 0 else "↓"
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {epic}: {bid:.2f}/{ask:.2f} {color}{arrow} {change_pct:+.2f}%{ConsoleAlert.COLORS['END']}", end='\r')
    
    @staticmethod
    def order_executed(epic: str, direction: str, size: float, price: float, deal_id: str):
        """Orden ejecutada"""
        color = ConsoleAlert.COLORS['GREEN'] if direction == "BUY" else ConsoleAlert.COLORS['RED']
        print(f"""
{ConsoleAlert.COLORS['BOLD']}╔══════════════════════════════════════════════════════════════╗
║  {color}💰 ORDEN EJECUTADA{ConsoleAlert.COLORS['END']}{ConsoleAlert.COLORS['BOLD']}                                          ║
╠══════════════════════════════════════════════════════════════╣{ConsoleAlert.COLORS['END']}
║  {ConsoleAlert.COLORS['CYAN']}Activo:{ConsoleAlert.COLORS['END']}    {epic}
║  {ConsoleAlert.COLORS['CYAN']}Dirección:{ConsoleAlert.COLORS['END']} {direction}
║  {ConsoleAlert.COLORS['CYAN']}Tamaño:{ConsoleAlert.COLORS['END']}    {size}
║  {ConsoleAlert.COLORS['CYAN']}Precio:{ConsoleAlert.COLORS['END']}    {price:.5f}
║  {ConsoleAlert.COLORS['CYAN']}Deal ID:{ConsoleAlert.COLORS['END']}   {deal_id}
{ConsoleAlert.COLORS['BOLD']}╚══════════════════════════════════════════════════════════════╝{ConsoleAlert.COLORS['END']}
""")


class CapitalComAPI:
    """Cliente API para Capital.com"""
    
    def __init__(self):
        self.session = requests.Session()
        self.cst = None
        self.token = None
        self.logged_in = False
        self.base_url = BASE_URL
        self.ws_url = "wss://api-streaming-capital.backend-capital.com/connect"
    
    def login(self) -> bool:
        """Autenticar con Capital.com"""
        url = f"{self.base_url}/session"
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
            else:
                ConsoleAlert.error(f"Error de autenticación: {r.status_code} - {r.text}")
        except Exception as e:
            ConsoleAlert.error(f"Error de conexión: {e}")
        return False
    
    def get_prices(self, epic: str, resolution: str = "HOUR", max_points: int = 200) -> Optional[pd.DataFrame]:
        """Obtener datos históricos"""
        if not self.logged_in:
            return None
        
        try:
            r = self.session.get(
                f"{self.base_url}/prices/{epic}",
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
            ConsoleAlert.error(f"Error obteniendo precios: {e}")
        return None
    
    def open_position(self, epic: str, direction: str, size: float, 
                      stop_loss: float = None, take_profit: float = None) -> Optional[str]:
        """Abrir una posición"""
        if not self.logged_in:
            return None
        
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size
        }
        
        if stop_loss:
            payload["stopLevel"] = stop_loss
        if take_profit:
            payload["profitLevel"] = take_profit
        
        try:
            r = self.session.post(f"{self.base_url}/positions", json=payload)
            
            if r.status_code == 200:
                data = r.json()
                deal_ref = data.get('dealReference')
                
                # Confirmar la operación
                time.sleep(0.5)
                confirm = self.session.get(f"{self.base_url}/confirms/{deal_ref}")
                
                if confirm.status_code == 200:
                    confirm_data = confirm.json()
                    if confirm_data.get('dealStatus') == 'ACCEPTED':
                        deal_id = confirm_data.get('dealId')
                        level = confirm_data.get('level')
                        ConsoleAlert.order_executed(epic, direction, size, level, deal_id)
                        return deal_id
                    else:
                        ConsoleAlert.error(f"Orden rechazada: {confirm_data.get('reason', 'Unknown')}")
                        return None
            else:
                ConsoleAlert.error(f"Error abriendo posición: {r.status_code} - {r.text}")
        except Exception as e:
            ConsoleAlert.error(f"Error en open_position: {e}")
        return None
    
    def close_position(self, deal_id: str) -> bool:
        """Cerrar una posición"""
        if not self.logged_in:
            return False
        
        try:
            r = self.session.delete(f"{self.base_url}/positions/{deal_id}")
            return r.status_code == 200
        except Exception as e:
            ConsoleAlert.error(f"Error cerrando posición: {e}")
        return False
    
    def get_account_balance(self) -> Optional[Dict]:
        """Obtener balance de la cuenta"""
        if not self.logged_in:
            return None
        
        try:
            r = self.session.get(f"{self.base_url}/accounts")
            if r.status_code == 200:
                data = r.json()
                accounts = data.get('accounts', [])
                for acc in accounts:
                    if acc.get('preferred'):
                        return acc.get('balance')
        except Exception as e:
            ConsoleAlert.error(f"Error obteniendo balance: {e}")
        return None


class SMCAnalyzer:
    """Analizador de Smart Money Concepts"""
    
    @staticmethod
    def detect_fvg(df: pd.DataFrame, min_gap_pct: float = 0.002) -> List[Dict]:
        """Detectar Fair Value Gaps"""
        fvgs = []
        
        for i in range(2, len(df)):
            # Bullish FVG
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gap_size = (df['low'].iloc[i] - df['high'].iloc[i-2]) / df['close'].iloc[i]
                if gap_size >= min_gap_pct:
                    fvgs.append({
                        'type': 'BULLISH_FVG',
                        'low': df['high'].iloc[i-2],
                        'high': df['low'].iloc[i],
                        'size_pct': gap_size * 100,
                        'timestamp': df['timestamp'].iloc[i]
                    })
            
            # Bearish FVG
            if df['high'].iloc[i] < df['low'].iloc[i-2]:
                gap_size = (df['low'].iloc[i-2] - df['high'].iloc[i]) / df['close'].iloc[i]
                if gap_size >= min_gap_pct:
                    fvgs.append({
                        'type': 'BEARISH_FVG',
                        'low': df['high'].iloc[i],
                        'high': df['low'].iloc[i-2],
                        'size_pct': gap_size * 100,
                        'timestamp': df['timestamp'].iloc[i]
                    })
        
        return fvgs[-5:] if fvgs else []
    
    @staticmethod
    def detect_order_blocks(df: pd.DataFrame, lookback: int = 20) -> List[Dict]:
        """Detectar Order Blocks"""
        order_blocks = []
        
        for i in range(lookback, len(df)):
            # Bullish OB
            if (df['close'].iloc[i-1] < df['open'].iloc[i-1] and
                df['close'].iloc[i] > df['open'].iloc[i] and
                df['close'].iloc[i] > df['high'].iloc[i-1] * 1.003):
                
                order_blocks.append({
                    'type': 'BULLISH_OB',
                    'low': df['low'].iloc[i-1],
                    'high': df['high'].iloc[i-1],
                    'strength': abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['open'].iloc[i]
                })
            
            # Bearish OB
            if (df['close'].iloc[i-1] > df['open'].iloc[i-1] and
                df['close'].iloc[i] < df['open'].iloc[i] and
                df['close'].iloc[i] < df['low'].iloc[i-1] * 0.997):
                
                order_blocks.append({
                    'type': 'BEARISH_OB',
                    'low': df['low'].iloc[i-1],
                    'high': df['high'].iloc[i-1],
                    'strength': abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['open'].iloc[i]
                })
        
        return sorted(order_blocks, key=lambda x: x['strength'], reverse=True)[:3]
    
    @staticmethod
    def calculate_premium_discount(df: pd.DataFrame) -> Dict:
        """Calcular zona Premium/Discount"""
        lookback = min(50, len(df))
        high = df['high'].iloc[-lookback:].max()
        low = df['low'].iloc[-lookback:].min()
        current = df['close'].iloc[-1]
        
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
            'low': low
        }
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> float:
        """Calcular RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return round(rsi.iloc[-1], 2)


class AutoTrader:
    """Sistema de trading automático"""
    
    def __init__(self, config: Dict = None):
        self.api = CapitalComAPI()
        self.analyzer = SMCAnalyzer()
        self.alert = ConsoleAlert()
        
        # Configuración por defecto
        self.config = config or {
            'assets': ['GOLD', 'US30'],
            'risk_per_trade_pct': 2.0,  # % del balance por trade
            'max_positions': 3,
            'min_confidence': 70,
            'check_interval': 60,  # segundos
        }
        
        # Estado
        self.running = False
        self.positions = {}
        self.alert_zones: List[AlertZone] = []
        self.last_prices: Dict[str, float] = {}
        
    def start(self):
        """Iniciar el bot"""
        ConsoleAlert.print_banner()
        
        ConsoleAlert.info("Conectando con Capital.com...")
        if not self.api.login():
            ConsoleAlert.error("No se pudo conectar. Verifica tus credenciales.")
            return
        
        ConsoleAlert.success("Conectado a Capital.com")
        
        # Mostrar balance
        balance = self.api.get_account_balance()
        if balance:
            ConsoleAlert.info(f"Balance: ${balance.get('balance', 0):.2f} | Disponible: ${balance.get('available', 0):.2f}")
        
        # Analizar mercados y establecer zonas de alerta
        self._setup_alert_zones()
        
        # Iniciar monitoreo
        self.running = True
        ConsoleAlert.info("Iniciando monitoreo de mercados...")
        self._monitoring_loop()
    
    def stop(self):
        """Detener el bot"""
        self.running = False
        ConsoleAlert.warning("Deteniendo bot...")
    
    def _setup_alert_zones(self):
        """Configurar zonas de alerta basadas en análisis SMC"""
        ConsoleAlert.info("Analizando mercados y configurando zonas de alerta...")
        
        for epic in self.config['assets']:
            ConsoleAlert.info(f"Analizando {epic}...")
            
            # Obtener datos H1
            df = self.api.get_prices(epic, "HOUR", 200)
            if df is None or len(df) < 50:
                ConsoleAlert.warning(f"No hay suficientes datos para {epic}")
                continue
            
            current_price = df['close'].iloc[-1]
            self.last_prices[epic] = current_price
            
            # Detectar FVGs
            fvgs = self.analyzer.detect_fvg(df)
            for fvg in fvgs:
                if fvg['type'] == 'BULLISH_FVG' and fvg['high'] < current_price:
                    # FVG alcista por debajo del precio = zona de demanda
                    zone = AlertZone(
                        epic=epic,
                        zone_type='BULLISH_FVG',
                        price_low=fvg['low'],
                        price_high=fvg['high'],
                        direction='LONG'
                    )
                    self.alert_zones.append(zone)
                    ConsoleAlert.info(f"  📍 Zona LONG: {fvg['low']:.2f} - {fvg['high']:.2f} (Bullish FVG)")
                
                elif fvg['type'] == 'BEARISH_FVG' and fvg['low'] > current_price:
                    # FVG bajista por encima del precio = zona de oferta
                    zone = AlertZone(
                        epic=epic,
                        zone_type='BEARISH_FVG',
                        price_low=fvg['low'],
                        price_high=fvg['high'],
                        direction='SHORT'
                    )
                    self.alert_zones.append(zone)
                    ConsoleAlert.info(f"  📍 Zona SHORT: {fvg['low']:.2f} - {fvg['high']:.2f} (Bearish FVG)")
            
            # Detectar Order Blocks
            obs = self.analyzer.detect_order_blocks(df)
            for ob in obs:
                if ob['type'] == 'BULLISH_OB' and ob['high'] < current_price:
                    zone = AlertZone(
                        epic=epic,
                        zone_type='BULLISH_OB',
                        price_low=ob['low'],
                        price_high=ob['high'],
                        direction='LONG'
                    )
                    self.alert_zones.append(zone)
                    ConsoleAlert.info(f"  📍 Zona LONG: {ob['low']:.2f} - {ob['high']:.2f} (Bullish OB)")
                
                elif ob['type'] == 'BEARISH_OB' and ob['low'] > current_price:
                    zone = AlertZone(
                        epic=epic,
                        zone_type='BEARISH_OB',
                        price_low=ob['low'],
                        price_high=ob['high'],
                        direction='SHORT'
                    )
                    self.alert_zones.append(zone)
                    ConsoleAlert.info(f"  📍 Zona SHORT: {ob['low']:.2f} - {ob['high']:.2f} (Bearish OB)")
            
            # Premium/Discount
            pd_zone = self.analyzer.calculate_premium_discount(df)
            ConsoleAlert.info(f"  📊 Zona actual: {pd_zone['zone']} ({pd_zone['position_pct']:.1f}%)")
            
            # RSI
            rsi = self.analyzer.calculate_rsi(df)
            ConsoleAlert.info(f"  📈 RSI(14): {rsi}")
        
        ConsoleAlert.success(f"Configuradas {len(self.alert_zones)} zonas de alerta")
    
    def _monitoring_loop(self):
        """Loop principal de monitoreo"""
        while self.running:
            try:
                for epic in self.config['assets']:
                    self._check_price_and_zones(epic)
                
                # Esperar intervalo configurado
                time.sleep(self.config['check_interval'])
                
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                ConsoleAlert.error(f"Error en loop de monitoreo: {e}")
                time.sleep(5)
    
    def _check_price_and_zones(self, epic: str):
        """Verificar precio actual contra zonas de alerta"""
        # Obtener precio actual
        df = self.api.get_prices(epic, "MINUTE", 5)
        if df is None or len(df) == 0:
            return
        
        current_price = df['close'].iloc[-1]
        
        # Actualizar display de precio
        prev_price = self.last_prices.get(epic, current_price)
        change_pct = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0
        self.last_prices[epic] = current_price
        
        # Verificar zonas de alerta
        for zone in self.alert_zones:
            if zone.epic != epic or not zone.active:
                continue
            
            # Verificar si el precio está en la zona
            if zone.price_low <= current_price <= zone.price_high:
                ConsoleAlert.warning(f"¡PRECIO EN ZONA! {epic} @ {current_price:.2f}")
                
                # Generar señal
                signal = self._generate_signal(epic, zone, current_price, df)
                
                if signal and signal.confidence >= self.config['min_confidence']:
                    ConsoleAlert.trade_alert(signal)
                    
                    # Ejecutar trade automáticamente
                    self._execute_trade(signal)
                    
                    # Desactivar zona para evitar múltiples entradas
                    zone.active = False
    
    def _generate_signal(self, epic: str, zone: AlertZone, current_price: float, df: pd.DataFrame) -> Optional[TradingSignal]:
        """Generar señal de trading basada en zona y confirmaciones"""
        
        # Obtener datos H1 para cálculos más precisos (el df de entrada puede ser MINUTE)
        df_h1 = self.api.get_prices(epic, "HOUR", 50)
        if df_h1 is None or len(df_h1) < 20:
            ConsoleAlert.warning(f"No hay suficientes datos H1 para {epic}")
            return None
        
        # Calcular confirmaciones
        confirmations = 0
        reasons = []
        
        # 1. RSI (usar datos H1)
        rsi = self.analyzer.calculate_rsi(df_h1)
        if pd.isna(rsi):
            rsi = 50  # Default neutral
        
        if zone.direction == 'LONG' and rsi < 40:
            confirmations += 1
            reasons.append(f"RSI sobreventa ({rsi})")
        elif zone.direction == 'SHORT' and rsi > 60:
            confirmations += 1
            reasons.append(f"RSI sobrecompra ({rsi})")
        
        # 2. Zona Premium/Discount (usar datos H1)
        pd_zone = self.analyzer.calculate_premium_discount(df_h1)
        if zone.direction == 'LONG' and pd_zone['zone'] == 'DISCOUNT':
            confirmations += 1
            reasons.append("Zona Discount")
        elif zone.direction == 'SHORT' and pd_zone['zone'] == 'PREMIUM':
            confirmations += 1
            reasons.append("Zona Premium")
        
        # 3. Tipo de zona (FVG vs OB)
        if 'FVG' in zone.zone_type:
            confirmations += 1
            reasons.append(zone.zone_type)
        elif 'OB' in zone.zone_type:
            confirmations += 1
            reasons.append(zone.zone_type)
        
        # Calcular confianza (máximo 100%)
        confidence = min(confirmations * 25 + 25, 100)
        
        if confidence < 50:
            return None
        
        # Calcular SL y TP usando ATR de H1
        atr = self._calculate_atr(df_h1)
        
        # Fallback si ATR es NaN o 0
        if pd.isna(atr) or atr <= 0:
            # Usar 0.5% del precio como ATR de emergencia
            atr = current_price * 0.005
            ConsoleAlert.warning(f"ATR no disponible, usando fallback: {atr:.2f}")
        
        if zone.direction == 'LONG':
            stop_loss = zone.price_low - (atr * 1.5)
            take_profit_1 = current_price + (atr * 2)
            take_profit_2 = current_price + (atr * 3)
            signal_type = SignalType.LONG
        else:
            stop_loss = zone.price_high + (atr * 1.5)
            take_profit_1 = current_price - (atr * 2)
            take_profit_2 = current_price - (atr * 3)
            signal_type = SignalType.SHORT
        
        # Validar que los valores son números válidos
        if pd.isna(stop_loss) or pd.isna(take_profit_1):
            ConsoleAlert.error("Error calculando SL/TP - valores inválidos")
            return None
        
        return TradingSignal(
            epic=epic,
            signal_type=signal_type,
            entry_price=current_price,
            stop_loss=round(stop_loss, 2),
            take_profit_1=round(take_profit_1, 2),
            take_profit_2=round(take_profit_2, 2),
            reason=", ".join(reasons),
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcular ATR con manejo de errores"""
        try:
            if len(df) < period + 1:
                # No hay suficientes datos, usar rango promedio simple
                return (df['high'] - df['low']).mean()
            
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=period).mean().iloc[-1]
            
            if pd.isna(atr):
                return (df['high'] - df['low']).mean()
            
            return atr
        except Exception as e:
            ConsoleAlert.warning(f"Error calculando ATR: {e}")
            return df['close'].iloc[-1] * 0.005  # 0.5% del precio como fallback
    
    def _execute_trade(self, signal: TradingSignal):
        """Ejecutar trade"""
        
        # Verificar número máximo de posiciones
        if len(self.positions) >= self.config['max_positions']:
            ConsoleAlert.warning(f"Máximo de posiciones alcanzado ({self.config['max_positions']})")
            return
        
        # Calcular tamaño de posición
        balance = self.api.get_account_balance()
        if not balance:
            ConsoleAlert.error("No se pudo obtener balance")
            return
        
        available = balance.get('available', 0)
        risk_amount = available * (self.config['risk_per_trade_pct'] / 100)
        
        # GOLD tiene peor rendimiento en backtest - reducir tamaño a la mitad
        if signal.epic == 'GOLD':
            risk_amount = risk_amount * 0.5
            ConsoleAlert.info(f"GOLD: tamaño reducido al 50% (backtest marginal)")
        
        # Calcular tamaño basado en riesgo
        risk_pips = abs(signal.entry_price - signal.stop_loss)
        size = risk_amount / risk_pips if risk_pips > 0 else 1
        size = max(1, min(size, 10))  # Limitar tamaño entre 1 y 10
        
        direction = "BUY" if signal.signal_type == SignalType.LONG else "SELL"
        
        ConsoleAlert.info(f"Ejecutando {direction} {signal.epic} x{size:.1f}")
        
        deal_id = self.api.open_position(
            epic=signal.epic,
            direction=direction,
            size=size,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit_1
        )
        
        if deal_id:
            self.positions[deal_id] = {
                'signal': signal,
                'size': size,
                'entry_time': datetime.now()
            }
            ConsoleAlert.success(f"Posición abierta: {deal_id}")
        else:
            ConsoleAlert.error("No se pudo abrir la posición")
    
    def add_manual_zone(self, epic: str, price_low: float, price_high: float, direction: str):
        """Añadir zona de alerta manual"""
        zone = AlertZone(
            epic=epic,
            zone_type='MANUAL',
            price_low=price_low,
            price_high=price_high,
            direction=direction.upper()
        )
        self.alert_zones.append(zone)
        ConsoleAlert.success(f"Zona manual añadida: {epic} {direction} @ {price_low}-{price_high}")


def main():
    """Función principal"""
    
    # Configuración personalizada
    config = {
        'assets': ['GOLD', 'US30'],
        'risk_per_trade_pct': 2.0,
        'max_positions': 2,
        'min_confidence': 60,
        'check_interval': 30,  # Revisar cada 30 segundos
    }
    
    trader = AutoTrader(config)
    
    # El bot detecta zonas automáticamente usando SMC
    # No se necesitan zonas manuales - siempre usa datos frescos
    
    try:
        trader.start()
    except KeyboardInterrupt:
        trader.stop()
        ConsoleAlert.info("Bot detenido por el usuario")


if __name__ == '__main__':
    main()
