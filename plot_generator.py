import json
import os
import re
from datetime import datetime
from typing import Dict, Any
import pandas as pd
import matplotlib.pyplot as plt


class PlotGenerator:
    """Minimal seed implementation intended for iterative agent-led evolution."""

    def __init__(self):
        self.version = 1
        self.history = []
        self.improvements = []
        self.plot_history = []  # NEW: backward-compatible list of generated plots
        # Core adjustable knobs (extend here)
        self.features = {
            "style": "ggplot",
            "figsize": (12, 6),
            "line_width": 2,
            "grid": True,
            "moving_avg": False,
            "peaks": False,
            "annotate": False,
            "volume": False,
        }
        # Keyword → feature toggle mapping (extend easily)
        self._keyword_map = {
            "ma": "moving_avg",
            "moving average": "moving_avg",
            "peak": "peaks",
            "high": "peaks",
            "low": "peaks",
            "annot": "annotate",
            "label": "annotate",
            "volume": "volume",
            "style": "style",
        }

    def evolve(self, feedback: str, improvement_type: str = "critic"):  # CHANGED signature
        """Backward-compatible evolve method (keeps optional improvement_type)."""
        self.version += 1
        fb_l = feedback.lower()
        # Feature toggles (unchanged logic)
        for k, feat in self._keyword_map.items():
            if k in fb_l:
                if feat == "style":
                    if "classic" in fb_l:
                        self.features["style"] = "classic"
                    elif "default" in fb_l:
                        self.features["style"] = "default"
                else:
                    self.features[feat] = True
        # Track improvement (NEW)
        self.improvements.append({
            "version": self.version,
            "feedback": feedback[:400],
            "type": improvement_type,
            "timestamp": datetime.now().isoformat()
        })
        # Keep lightweight history entry too
        self.history.append({"version": self.version, "feedback": feedback, "ts": datetime.now().isoformat()})

    def _apply_style(self):
        try:
            plt.style.use(self.features.get("style", "default"))
        except Exception:
            pass  # silent fallback

    def plot_stock_prices(self, data: Dict[str, pd.DataFrame], filename: str = "ytd_stock_gains.png") -> str:
        self._apply_style()
        use_volume = self.features["volume"]
        if use_volume:
            fig, (ax, axv) = plt.subplots(2, 1, figsize=self.features["figsize"], gridspec_kw={'height_ratios': [3, 1]})
        else:
            fig, ax = plt.subplots(figsize=self.features["figsize"])

        for symbol, df in data.items():
            if df.empty:
                continue
            base = df['Close'].iloc[0]
            pct = (df['Close'] / base - 1) * 100.0
            line = ax.plot(df.index, pct, label=symbol, linewidth=self.features["line_width"])
            color = line[0].get_color()

            if self.features["moving_avg"] and len(pct) > 20:
                ax.plot(df.index, pct.rolling(20).mean(), '--', linewidth=1, alpha=0.7, label=f"{symbol} MA20", color=color)

            if self.features["peaks"]:
                ax.scatter([pct.idxmax()], [pct.max()], marker='^', color='green', s=60, zorder=5)
                ax.scatter([pct.idxmin()], [pct.min()], marker='v', color='red', s=60, zorder=5)

            if self.features["annotate"]:
                ax.annotate(f"{pct.iloc[-1]:.1f}%", xy=(df.index[-1], pct.iloc[-1]),
                            xytext=(6, 4), textcoords="offset points",
                            fontsize=8, bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.5))

            if use_volume and 'Volume' in df.columns:
                axv.bar(df.index, df['Volume'], alpha=0.25, color=color, label=f"{symbol} Vol")

        ax.set_title(f"YTD Stock Gains {datetime.now().year} (v{self.version})")
        ax.set_ylabel("Gain (%)")
        ax.axhline(0, color='black', linewidth=0.5, alpha=0.6)
        if self.features["grid"]:
            ax.grid(alpha=0.3)
        ax.legend()

        if use_volume:
            axv.set_ylabel("Volume")
            axv.grid(alpha=0.2)
            axv.legend(fontsize=8)

        plt.tight_layout()

        if not re.search(r'_v\d+', filename):
            filename = filename.replace(".png", f"_v{self.version}.png")

        plt.savefig(filename, dpi=160)
        plt.close()
        # NEW: append to plot_history (app expects this)
        self.plot_history.append({
            "version": self.version,
            "filename": filename,
            "features": {k: v for k, v in self.features.items() if v},
            "timestamp": datetime.now().isoformat()
        })
        # Keep legacy summary history (unchanged)
        self.history.append({
            "version": self.version,
            "file": filename,
            "features": {k: v for k, v in self.features.items() if v},
            "ts": datetime.now().isoformat()
        })
        return filename

    def summary(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "active_features": {k: v for k, v in self.features.items() if v and v is not False},
            "recent": self.history[-5:]
        }

    def get_evolution_summary(self) -> Dict[str, Any]:  # NEW: compatibility with app expectations
        return {
            "current_version": self.version,
            "total_improvements": len(self.improvements),
            "active_features": {k: v for k, v in self.features.items() if v and v != "default"},
            "improvement_history": self.improvements[-5:] if self.improvements else []
        }

    def save_state(self, path: str = "plot_state.json"):
        with open(path, "w") as f:
            json.dump({
                "version": self.version,
                "features": self.features,
                "history": self.history,
                "improvements": self.improvements,
                "plot_history": self.plot_history  # NEW
            }, f, indent=2)

    def load_state(self, path: str = "plot_state.json"):
        if not os.path.exists(path):
            return
        with open(path) as f:
            state = json.load(f)
        self.version = state.get("version", self.version)
        self.features.update(state.get("features", {}))
        self.history = state.get("history", self.history)
        self.improvements = state.get("improvements", self.improvements)
        self.plot_history = state.get("plot_history", self.plot_history)  # NEW
