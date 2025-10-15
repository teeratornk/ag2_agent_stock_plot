import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# ---------------------------- Configuration ----------------------------------
symbols = ["NVDA", "TSLA"]          # Primary symbols
benchmark = "^GSPC"                 # S&P 500 index as benchmark
all_symbols = symbols + [benchmark]

ma_windows = [20, 50]               # Moving-average windows in trading days
line_width = 2.0                    # Line width for YTD return plot
figsize = (14, 10)                  # Overall figure size
peak_lookaround = 2                 # Neighbours to compare for peak detection
annotate_peaks = 3                  # Annotate this many most-recent peaks

# ---------------------------- Style handling ---------------------------------
for style in ("ggplot", "classic", "default"):
    try:
        try:
            plt.style.use(style)
        except OSError:
            for _s in ['ggplot','classic','default']:
                try:
                    plt.style.use(_s)
                    break
                except OSError:
                    pass
        break
    except Exception:
        continue

# ---------------------------- Data download ----------------------------------
today = dt.datetime.today().date()
year_start = dt.date(today.year, 1, 1)

data = yf.download(
    tickers=all_symbols,
    start=year_start,
    end=today + dt.timedelta(days=1),
    progress=False,
    group_by="ticker",
    auto_adjust=False,
)

# ---------------------------- Helper extraction ------------------------------
def get_adjusted_close(df, ticker):
    """Return a Series of adjusted close for a given ticker from yfinance download output."""
    if isinstance(df.columns, pd.MultiIndex):
        return df[ticker]["Adj Close"].dropna()
    # Single-index frame occurs when only one symbol was requested
    return df["Adj Close"].dropna()

def get_volume(df, ticker):
    if isinstance(df.columns, pd.MultiIndex):
        return df[ticker]["Volume"].dropna()
    return df["Volume"].dropna()

adj_close = {s: get_adjusted_close(data, s) for s in all_symbols}
volume = {s: get_volume(data, s) for s in symbols}

# ---------------------------- YTD % change -----------------------------------
def ytd_percent_change(series: pd.Series) -> pd.Series:
    """Compute YTD percent change using the first trading day of the year."""
    if series.empty:
        return series
    first_val = series.loc[series.first_valid_index()]
    return (series / first_val - 1.0) * 100.0

ytd = {s: ytd_percent_change(adj_close[s]) for s in all_symbols}

# ---------------------------- Moving averages --------------------------------
ma = {
    s: {w: adj_close[s].rolling(window=w).mean() for w in ma_windows}
    for s in symbols
}

# ---------------------------- Peak detection ---------------------------------
def find_peaks(series: pd.Series, lookaround: int = 2) -> pd.Series:
    """Return boolean Series where local peaks are True."""
    if series.empty:
        return pd.Series(dtype=bool)
    larger_than_prev = series > series.shift(1)
    larger_than_next = series > series.shift(-1)
    is_peak = larger_than_prev & larger_than_next
    # Further ensure peaks dominate a window around them
    for i in range(2, lookaround + 1):
        is_peak &= (series > series.shift(i)) & (series > series.shift(-i))
    return is_peak

peaks = {s: find_peaks(adj_close[s], peak_lookaround) for s in symbols}

# ---------------------------- Plotting ---------------------------------------
fig, axes = plt.subplots(
    nrows=3, ncols=1, figsize=figsize, sharex=False, gridspec_kw={"height_ratios": [3, 3, 2]}
)

# --- Price + Moving Averages + Volume for each symbol ---
for ax_idx, sym in enumerate(symbols):
    ax_price = axes[ax_idx]
    ax_vol = ax_price.twinx()

    # Price line
    ax_price.plot(adj_close[sym].index, adj_close[sym], label=f"{sym} Price", color="tab:blue", lw=1.5)

    # Moving averages
    for w, col in zip(ma_windows, ["tab:orange", "tab:green"]):
        ax_price.plot(ma[sym][w].index, ma[sym][w], label=f"{w}-DMA", color=col, lw=1.2, alpha=0.8)

    # Peaks annotation
    peak_idx = peaks[sym][peaks[sym]].index[-annotate_peaks:]
    for idx in peak_idx:
        price_val = adj_close[sym].loc[idx]
        ax_price.scatter(idx, price_val, color="red", zorder=5)
        ax_price.annotate(
            f"{price_val:.2f}",
            xy=(idx, price_val),
            xytext=(0, 5),
            textcoords="offset points",
            fontsize=8,
            color="red",
        )

    # Volume bars
    ax_vol.bar(volume[sym].index, volume[sym] / 1e6, color="lightgrey", alpha=0.4, label="Volume (M)")
    ax_vol.set_ylabel("Volume (Millions)")
    ax_vol.tick_params(axis='y', labelsize=8)

    # Axis formatting
    ax_price.set_title(f"{sym} Price, MAs & Peaks")
    ax_price.set_ylabel("Price (USD)")
    ax_price.grid(True, which="both", linestyle="--", alpha=0.4)
    lines, labels = ax_price.get_legend_handles_labels()
    lines2, labels2 = ax_vol.get_legend_handles_labels()
    ax_price.legend(lines + lines2, labels + labels2, fontsize=8, loc="upper left")

# --- YTD % Change plot for symbols & benchmark ---
ax_ytd = axes[2]
for sym, col in zip(all_symbols, ["tab:blue", "tab:green", "tab:gray"]):
    ax_ytd.plot(ytd[sym].index, ytd[sym], label=sym, lw=line_width, color=col)

ax_ytd.set_title(f"YTD % Change ({today.year})")
ax_ytd.set_xlabel("Date")
ax_ytd.set_ylabel("Return (%)")
ax_ytd.axhline(0, color="black", linewidth=0.8, linestyle="--")
ax_ytd.grid(True, which="both", linestyle="--", alpha=0.4)
ax_ytd.legend()

# ---------------------------- Final touches ----------------------------------
plt.suptitle(f"{today.year} YTD Stock Performance: NVDA & TSLA vs S&P 500", fontsize=14, y=0.99)
plt.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig("ytd_stock_gains.png", dpi=300)