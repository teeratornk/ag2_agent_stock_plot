from typing import List, Dict, Any
from datetime import datetime
import os

class CodeGenerator:
    """Generate standalone executable code based on current system state"""
    
    @staticmethod
    def generate_plot_code(symbols: List[str], plot_generator: Any, stock_service: Any) -> str:
        """Generate standalone Python code for plotting stocks"""
        
        # Start with imports
        code = """import yfinance as yf
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from datetime import datetime
import os

# Stock symbols to analyze
symbols = {symbols}

# Fetch stock data
print("Fetching stock data...")
data = {{}}
start_date = f"{{datetime.now().year}}-01-01"

for symbol in symbols:
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date)
        if not df.empty:
            data[symbol] = df
            print(f"✓ Fetched data for {{symbol}}")
        else:
            print(f"✗ No data for {{symbol}}")
    except Exception as e:
        print(f"✗ Error fetching {{symbol}}: {{e}}")

if not data:
    print("ERROR: No stock data fetched!")
    exit(1)

# Create the plot
print("Creating plot...")
""".format(symbols=symbols)
        
        # Add plot configuration based on features
        features = plot_generator.current_features
        
        # Set up figure
        if features.get("volume_subplot"):
            code += """fig, (ax1, ax2) = plt.subplots(2, 1, figsize={}, gridspec_kw={{'height_ratios': [3, 1]}})
""".format(features["figure_size"])
        else:
            code += """fig, ax1 = plt.subplots(figsize={})
""".format(features["figure_size"])
        
        # Add main plotting logic
        code += """
# Plot each stock
for idx, (symbol, df) in enumerate(data.items()):
    # Calculate percentage change from start of year
    initial_price = df['Close'].iloc[0]
    pct_change = ((df['Close'] - initial_price) / initial_price) * 100
    
    # Main price line
    line = ax1.plot(df.index, pct_change, label=symbol, linewidth={})
""".format(features.get("line_width", 2))
        
        # Add feature-specific code
        if features.get("moving_average"):
            code += """    
    # Add moving average
    if len(df) > 20:
        ma20 = pct_change.rolling(window=20).mean()
        ax1.plot(df.index, ma20, '--', label=f"{{symbol}} MA20", alpha=0.7)
"""
        
        if features.get("annotations"):
            code += """    
    # Add annotations
    latest_value = pct_change.iloc[-1]
    ax1.annotate(f'{{latest_value:.1f}}%', 
                xy=(df.index[-1], latest_value),
                xytext=(10, 5), textcoords='offset points',
                fontsize=9, bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
"""
        
        if features.get("highlight_peaks"):
            code += """    
    # Highlight peaks and valleys
    max_idx = pct_change.idxmax()
    min_idx = pct_change.idxmin()
    ax1.scatter([max_idx], [pct_change[max_idx]], color='green', s=100, zorder=5, marker='^')
    ax1.scatter([min_idx], [pct_change[min_idx]], color='red', s=100, zorder=5, marker='v')
"""
        
        if features.get("volume_subplot"):
            code += """    
    # Add volume subplot
    if 'Volume' in df.columns:
        ax2.bar(df.index, df['Volume'], alpha=0.3, label=f"{{symbol}} Volume")
"""
        
        # Configure plot
        code += """
# Configure main plot
ax1.set_title(f"YTD Stock Gains - {{datetime.now().year}} (v{})", fontsize={})
ax1.set_xlabel("Date", fontsize={})
ax1.set_ylabel("Gain (%)", fontsize={})
ax1.legend(loc='best')
ax1.grid({}, alpha={})
ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)
""".format(
            plot_generator.version,
            features.get("title_size", 16),
            features.get("label_size", 12),
            features.get("label_size", 12),
            features.get("grid", True),
            features.get("grid_alpha", 0.3)
        )
        
        if features.get("volume_subplot"):
            code += """
# Configure volume subplot
ax2.set_xlabel("Date", fontsize={})
ax2.set_ylabel("Volume", fontsize={})
ax2.legend(loc='best')
ax2.grid(True, alpha=0.3)
""".format(features.get("label_size", 12), features.get("label_size", 12))
        
        # Save the plot
        code += """
# Save the plot
plt.tight_layout()

# Ensure the output directory exists and save there
output_dir = 'coding'
os.makedirs(output_dir, exist_ok=True)
output_file = os.path.join(output_dir, 'ytd_stock_gains.png')

plt.savefig(output_file, dpi={}, bbox_inches='tight')
plt.close()

print(f"✓ Plot saved as {{output_file}}")
""".format(features.get("dpi", 300))
        
        return code
    
    @staticmethod
    def save_generated_code(code: str, filepath: str):
        """Save generated code to file"""
        with open(filepath, 'w') as f:
            f.write(code)

