import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
import json
import os


class StockDataService:
    """Minimal seed service intended for agent-driven evolutionary expansion."""

    def __init__(self):
        self.version = 1
        # Core capabilities (extend here)
        self.capabilities = {
            "prices": True,
            "moving_avg": False,
            "rsi": False,
            "volatility": False,
            "correlation": False,
            "volume": False,
        }
        # Feedback keyword mapping (extendable)
        self._kw_map = {
            "ma": "moving_avg", "moving average": "moving_avg",
            "rsi": "rsi", "relative strength": "rsi",
            "vol": "volatility", "volatility": "volatility", "risk": "volatility",
            "corr": "correlation", "correlation": "correlation",
            "volume": "volume"
        }
        self.history = []
        self.cache: Dict[str, pd.DataFrame] = {}

    def evolve(self, feedback: str):
        """Toggle capabilities inferred from feedback; bump version."""
        self.version += 1
        fb = feedback.lower()
        for k, cap in self._kw_map.items():
            if k in fb:
                self.capabilities[cap] = True
        self.history.append({
            "version": self.version,
            "feedback": feedback[:160],
            "active": [k for k, v in self.capabilities.items() if v],
            "ts": datetime.now().isoformat()
        })

    def clear_cache(self, symbols: Optional[List[str]] = None):
        if symbols is None:
            self.cache.clear()
        else:
            for s in symbols:
                self.cache.pop(s, None)

    def get_stock_prices(self, symbols: List[str], start_date: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """Fetch + lightweight enrich; caches per symbol."""
        if not start_date:
            start_date = f"{datetime.now().year}-01-01"
        out: Dict[str, pd.DataFrame] = {}
        for sym in symbols:
            df = self.cache.get(sym)
            if df is None or df.empty:
                try:
                    df = yf.Ticker(sym).history(start=start_date)
                except Exception:
                    df = pd.DataFrame()
                self.cache[sym] = df
            if not df.empty:
                if self.capabilities["moving_avg"]:
                    self._add_moving_avg(df)
                if self.capabilities["rsi"]:
                    self._add_rsi(df)
                if self.capabilities["volatility"]:
                    df.attrs["volatility"] = self._annualized_vol(df)
            out[sym] = df
        return out

    def calculate_ytd_gains(self, data: Dict[str, pd.DataFrame]) -> Dict[str, float]:
        gains = {}
        for sym, df in data.items():
            if not df.empty:
                gains[sym] = (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100
        return gains

    def get_enhanced_metrics(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Return minimal metrics; extend as evolution proceeds."""
        metrics: Dict[str, Dict[str, Any]] = {}
        for sym in symbols:
            df = self.cache.get(sym)
            if df is None or df.empty:
                continue
            m: Dict[str, Any] = {
                "ytd_gain": (df['Close'].iloc[-1] / df['Close'].iloc[0] - 1) * 100,
                "price": df['Close'].iloc[-1]
            }
            if self.capabilities["volatility"]:
                m["volatility"] = df.attrs.get("volatility", self._annualized_vol(df))
            if self.capabilities["rsi"] and 'RSI' in df.columns:
                m["rsi"] = float(df['RSI'].iloc[-1])
            metrics[sym] = m
        return metrics

    def get_correlation_matrix(self, symbols: List[str]) -> pd.DataFrame:
        if not self.capabilities["correlation"] or len(symbols) < 2:
            return pd.DataFrame()
        closes = {}
        for s in symbols:
            df = self.cache.get(s)
            if df is not None and not df.empty:
                closes[s] = df['Close']
        if not closes:
            return pd.DataFrame()
        return pd.DataFrame(closes).pct_change().corr()

    # --- Helpers (kept tiny; extension hooks) ---
    def _add_moving_avg(self, df: pd.DataFrame):
        if 'MA20' not in df.columns:
            df['MA20'] = df['Close'].rolling(20).mean()

    def _add_rsi(self, df: pd.DataFrame, period: int = 14):
        if 'RSI' in df.columns:
            return
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        df['RSI'] = 100 - (100 / (1 + rs))

    def _annualized_vol(self, df: pd.DataFrame) -> float:
        if df.empty or len(df) < 2:
            return 0.0
        r = df['Close'].pct_change().dropna()
        return float(r.std() * np.sqrt(252) * 100)

    # --- Introspection / persistence ---
    def summary(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "active_capabilities": [k for k, v in self.capabilities.items() if v],
            "recent_history": self.history[-5:],
            "cache_symbols": list(self.cache.keys())
        }

    def save_state(self, path: str = "stock_service_state.json"):
        with open(path, "w") as f:
            json.dump({
                "version": self.version,
                "capabilities": self.capabilities,
                "history": self.history
            }, f, indent=2)

    def load_state(self, path: str = "stock_service_state.json"):
        if not os.path.exists(path):
            return
        with open(path) as f:
            state = json.load(f)
        self.version = state.get("version", self.version)
        self.capabilities.update(state.get("capabilities", {}))
        self.history = state.get("history", self.history)
