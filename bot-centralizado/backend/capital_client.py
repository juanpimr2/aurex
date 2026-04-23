"""
Capital.com API Client
======================
Wrapper limpio para la API de Capital.com.
Las credenciales se cargan desde .env, NUNCA hardcodeadas.
"""
import os
import time
import requests
import pandas as pd
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()


class CapitalClient:
    DEMO_URL = "https://demo-api-capital.backend-capital.com/api/v1"
    REAL_URL = "https://api-capital.backend-capital.com/api/v1"

    def __init__(self):
        self.api_key = os.getenv("CAPITAL_API_KEY", "")
        self.password = os.getenv("CAPITAL_PASSWORD", "")
        self.email = os.getenv("CAPITAL_EMAIL", "")
        mode = os.getenv("CAPITAL_MODE", "DEMO").upper()
        self.base_url = self.DEMO_URL if mode == "DEMO" else self.REAL_URL
        self.is_demo = mode == "DEMO"

        self.session = requests.Session()
        self.is_logged_in = False

    def login(self) -> bool:
        headers = {"X-CAP-API-KEY": self.api_key, "Content-Type": "application/json"}
        data = {"identifier": self.email, "password": self.password}
        try:
            r = self.session.post(f"{self.base_url}/session", headers=headers, json=data, timeout=10)
            if r.status_code == 200:
                self.session.headers.update({
                    "X-SECURITY-TOKEN": r.headers.get("X-SECURITY-TOKEN", ""),
                    "CST": r.headers.get("CST", ""),
                    "Content-Type": "application/json",
                })
                self.is_logged_in = True
                return True
            print(f"[CapitalClient] Login failed: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"[CapitalClient] Login error: {e}")
        return False

    def ensure_session(self) -> bool:
        """Re-autenticar si la sesión expiró"""
        if not self.is_logged_in:
            return self.login()
        # Capital.com sessions expire after 10 minutes of inactivity
        # Try a lightweight ping, re-login if needed
        try:
            r = self.session.get(f"{self.base_url}/accounts", timeout=5)
            if r.status_code == 401:
                self.is_logged_in = False
                return self.login()
            return True
        except Exception:
            return self.login()

    def get_prices(
        self, epic: str, resolution: str = "HOUR", max_points: int = 1000
    ) -> Optional[pd.DataFrame]:
        """
        Obtener datos OHLCV históricos.

        Resoluciones válidas: MINUTE, MINUTE_5, MINUTE_15, MINUTE_30,
                              HOUR, HOUR_4, DAY, WEEK
        """
        if not self.ensure_session():
            return None
        try:
            r = self.session.get(
                f"{self.base_url}/prices/{epic}",
                params={"resolution": resolution, "max": max_points},
                timeout=15,
            )
            if r.status_code == 200:
                prices = r.json().get("prices", [])
                if not prices:
                    return None
                rows = []
                for c in prices:
                    vol = c.get("lastTradedVolume", 0)
                    rows.append({
                        "timestamp": pd.to_datetime(c["snapshotTime"]),
                        "open": float(c["openPrice"]["bid"]),
                        "high": float(c["highPrice"]["bid"]),
                        "low": float(c["lowPrice"]["bid"]),
                        "close": float(c["closePrice"]["bid"]),
                        "volume": float(vol) if vol else 1.0,
                    })
                df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
                return df
            print(f"[CapitalClient] get_prices error: {r.status_code}")
        except Exception as e:
            print(f"[CapitalClient] get_prices exception: {e}")
        return None

    def get_balance(self) -> Optional[Dict]:
        if not self.ensure_session():
            return None
        try:
            r = self.session.get(f"{self.base_url}/accounts", timeout=10)
            if r.status_code == 200:
                for acc in r.json().get("accounts", []):
                    if acc.get("preferred"):
                        bal = acc.get("balance", {})
                        return {
                            "balance": float(bal.get("balance", 0)),
                            "available": float(bal.get("available", 0)),
                            "profit_loss": float(bal.get("profitLoss", 0)),
                        }
        except Exception as e:
            print(f"[CapitalClient] get_balance error: {e}")
        return None

    def get_positions(self) -> List[Dict]:
        if not self.ensure_session():
            return []
        try:
            r = self.session.get(f"{self.base_url}/positions", timeout=10)
            if r.status_code == 200:
                positions = []
                for p in r.json().get("positions", []):
                    pos = p.get("position", {})
                    market = p.get("market", {})
                    positions.append({
                        "deal_id": pos.get("dealId"),
                        "epic": market.get("epic"),
                        "direction": pos.get("direction"),
                        "size": pos.get("size"),
                        "entry_price": pos.get("level"),
                        "stop_loss": pos.get("stopLevel"),
                        "take_profit": pos.get("profitLevel"),
                        "profit_loss": pos.get("upl", 0),
                        "created_at": pos.get("createdDateUTC"),
                    })
                return positions
        except Exception as e:
            print(f"[CapitalClient] get_positions error: {e}")
        return []

    def open_position(
        self,
        epic: str,
        direction: str,
        size: float,
        stop_loss: float = None,
        take_profit: float = None,
    ) -> Optional[str]:
        """
        Abrir posición. direction = 'BUY' o 'SELL'.
        Devuelve deal_id si se acepta, None si falla.
        """
        if not self.ensure_session():
            return None
        payload = {"epic": epic, "direction": direction, "size": size}
        if stop_loss is not None:
            payload["stopLevel"] = round(stop_loss, 2)
        if take_profit is not None:
            payload["profitLevel"] = round(take_profit, 2)

        try:
            r = self.session.post(f"{self.base_url}/positions", json=payload, timeout=10)
            if r.status_code == 200:
                deal_ref = r.json().get("dealReference")
                time.sleep(0.5)
                confirm = self.session.get(f"{self.base_url}/confirms/{deal_ref}", timeout=10)
                if confirm.status_code == 200:
                    data = confirm.json()
                    if data.get("dealStatus") == "ACCEPTED":
                        return data.get("dealId")
                    print(f"[CapitalClient] Order rejected: {data.get('reason')}")
            else:
                print(f"[CapitalClient] open_position error: {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"[CapitalClient] open_position exception: {e}")
        return None

    def modify_position(self, deal_id: str, stop_loss: float = None, take_profit: float = None) -> bool:
        """Modificar SL/TP de una posicion abierta."""
        if not self.ensure_session():
            return False
        payload = {}
        if stop_loss is not None:
            payload["stopLevel"] = round(stop_loss, 2)
        if take_profit is not None:
            payload["profitLevel"] = round(take_profit, 2)
        if not payload:
            return False
        try:
            r = self.session.put(f"{self.base_url}/positions/{deal_id}", json=payload, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"[CapitalClient] modify_position error: {e}")
        return False

    def close_position(self, deal_id: str) -> bool:
        if not self.ensure_session():
            return False
        try:
            r = self.session.delete(f"{self.base_url}/positions/{deal_id}", timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"[CapitalClient] close_position error: {e}")
        return False

    def get_market_info(self, epic: str) -> Optional[Dict]:
        if not self.ensure_session():
            return None
        try:
            r = self.session.get(f"{self.base_url}/markets/{epic}", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return None
