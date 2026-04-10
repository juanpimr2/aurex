"""
Live Trader
===========
Ejecuta la estrategia en tiempo real contra Capital.com.
Corre en un hilo separado, el API de FastAPI lo controla.
"""
import time
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Callable

from capital_client import CapitalClient
from strategy import StrategyConfig, get_latest_signal, get_position_size

logger = logging.getLogger("trader")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


class LiveTrader:
    def __init__(
        self,
        epic: str = "GOLD",
        timeframe: str = "HOUR",
        risk_pct: float = 1.5,
        max_positions: int = 2,
        check_interval: int = 60,
        strategy_cfg: StrategyConfig = None,
        on_event: Callable[[dict], None] = None,
    ):
        self.epic = epic
        self.timeframe = timeframe
        self.risk_pct = risk_pct
        self.max_positions = max_positions
        self.check_interval = check_interval
        self.cfg = strategy_cfg or StrategyConfig()
        self.on_event = on_event  # Callback para mandar eventos al WebSocket

        self.client = CapitalClient()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.trade_log: List[dict] = []
        self.status: dict = {
            "running": False,
            "epic": epic,
            "timeframe": timeframe,
            "last_check": None,
            "last_signal": None,
            "error": None,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Control
    # ──────────────────────────────────────────────────────────────────────

    def start(self) -> bool:
        with self._lock:
            if self._running:
                return False
            if not self.client.login():
                self.status["error"] = "No se pudo conectar a Capital.com"
                self._emit("error", {"message": "Login failed"})
                return False
            self._running = True
            self.status["running"] = True
            self.status["error"] = None
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            self._emit("started", {"epic": self.epic, "timeframe": self.timeframe})
            logger.info(f"Trader iniciado: {self.epic} @ {self.timeframe}")
            return True

    def stop(self):
        with self._lock:
            self._running = False
            self.status["running"] = False
        self._emit("stopped", {})
        logger.info("Trader detenido")

    # ──────────────────────────────────────────────────────────────────────
    # Loop principal
    # ──────────────────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                self._check_and_trade()
            except Exception as e:
                logger.error(f"Error en loop: {e}")
                self.status["error"] = str(e)
                self._emit("error", {"message": str(e)})
                time.sleep(5)
            time.sleep(self.check_interval)

    def _check_and_trade(self):
        now = datetime.now().strftime("%H:%M:%S")
        self.status["last_check"] = now

        # Obtener datos
        df = self.client.get_prices(self.epic, self.timeframe, max_points=200)
        if df is None or len(df) < 50:
            logger.warning(f"No hay suficientes datos para {self.epic}")
            return

        # Obtener señal
        signal = get_latest_signal(df, self.cfg)
        self.status["last_signal"] = signal

        # Precio actual
        current_price = float(df["close"].iloc[-1])
        balance = self.client.get_balance()
        equity = balance.get("balance", 0) if balance else 0

        self._emit("price_update", {
            "epic": self.epic,
            "price": current_price,
            "equity": equity,
            "timestamp": now,
        })

        # Verificar posiciones abiertas
        positions = self.client.get_positions()
        open_for_epic = [p for p in positions if p.get("epic") == self.epic]

        if signal is None:
            return

        logger.info(f"Señal: {signal['direction']} @ {signal['entry_price']:.2f} | RSI={signal['rsi']:.1f} | ATR={signal['atr']:.2f}")

        # No abrir si ya hay posición en esa dirección
        if open_for_epic:
            existing_dirs = [p["direction"] for p in open_for_epic]
            if signal["direction"] in existing_dirs:
                logger.info("Ya hay una posición abierta en esa dirección, omitiendo")
                return

        if len(positions) >= self.max_positions:
            logger.info(f"Máximo de posiciones alcanzado ({self.max_positions})")
            return

        # Calcular tamaño
        sl_dist = signal["sl_distance"]
        size = get_position_size(equity, sl_dist, self.risk_pct)

        # Loguear la operación antes de ejecutar
        logger.info(
            f"Abriendo {signal['direction']} {self.epic} | "
            f"Size: {size:.2f} | SL: {signal['stop_loss']:.2f} | TP: {signal['take_profit']:.2f}"
        )

        deal_id = self.client.open_position(
            epic=self.epic,
            direction=signal["direction"],
            size=size,
            stop_loss=signal["stop_loss"],
            take_profit=signal["take_profit"],
        )

        if deal_id:
            entry = {
                "deal_id": deal_id,
                "epic": self.epic,
                "direction": signal["direction"],
                "entry_price": signal["entry_price"],
                "stop_loss": signal["stop_loss"],
                "take_profit": signal["take_profit"],
                "size": size,
                "timestamp": datetime.now().isoformat(),
            }
            self.trade_log.append(entry)
            self._emit("trade_opened", entry)
            logger.info(f"Posición abierta: {deal_id}")
        else:
            logger.error("No se pudo abrir la posición")
            self._emit("error", {"message": "No se pudo abrir la posición"})

    # ──────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────

    def _emit(self, event_type: str, data: dict):
        if self.on_event:
            try:
                self.on_event({"type": event_type, "data": data, "ts": datetime.now().isoformat()})
            except Exception:
                pass

    def get_status(self) -> dict:
        positions = []
        if self.client.is_logged_in:
            positions = self.client.get_positions()
        balance = None
        if self.client.is_logged_in:
            balance = self.client.get_balance()
        return {
            **self.status,
            "positions": positions,
            "balance": balance,
            "trade_log": self.trade_log[-20:],  # últimos 20
        }
