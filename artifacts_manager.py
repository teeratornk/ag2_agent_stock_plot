import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import pandas as pd
import re

class ArtifactsManager:
    """Manage artifacts and code evolution history"""
    
    def __init__(self, base_dir: str = "artifacts"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)
        self.current_case_dir = None
        self.case_name = None
        self.metadata = {}
        
    def create_case(self, case_name: str, symbols: List[str]) -> Path:
        """Create a new case folder with timestamp"""
        # Clean the case name to avoid date duplication
        # Check if case_name already contains a date pattern (YYYYMMDD)
        date_pattern = r'\d{8}'
        
        # Get current date and time components
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")
        time_str = now.strftime("%H%M%S")
        
        # Check if the case name already contains today's date
        if re.search(date_pattern, case_name):
            # If it already has a date, just add the time
            self.case_name = f"{case_name}_{time_str}"
        else:
            # If no date in the name, add full timestamp
            self.case_name = f"{case_name}_{date_str}_{time_str}"
        
        self.current_case_dir = self.base_dir / self.case_name
        self.current_case_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize metadata
        self.metadata = {
            "case_name": case_name,
            "symbols": symbols,
            "timestamp": now.strftime("%Y%m%d_%H%M%S"),
            "created_at": now.isoformat(),
            "iterations": []
        }
        
        # Create subdirectories
        (self.current_case_dir / "plots").mkdir(exist_ok=True)
        (self.current_case_dir / "code").mkdir(exist_ok=True)
        (self.current_case_dir / "feedback").mkdir(exist_ok=True)
        (self.current_case_dir / "data").mkdir(exist_ok=True)
        (self.current_case_dir / "states").mkdir(exist_ok=True)
        
        self._save_metadata()
        return self.current_case_dir
    
    def save_iteration(self, 
                      iteration: int,
                      iteration_type: str,  # "critic" or "user"
                      plot_generator: Any,
                      stock_service: Any,
                      feedback: str = None,
                      plot_path: str = None,
                      stock_data: Dict[str, pd.DataFrame] = None) -> Dict[str, str]:
        """Save artifacts for current iteration"""
        if not self.current_case_dir:
            raise ValueError("No active case. Call create_case first.")
        
        iteration_id = f"v{iteration:03d}_{iteration_type}"
        saved_artifacts = {}
        
        # Save plot if exists
        if plot_path and os.path.exists(plot_path):
            plot_dest = self.current_case_dir / "plots" / f"{iteration_id}_plot.png"
            shutil.copy2(plot_path, plot_dest)
            saved_artifacts["plot"] = str(plot_dest)
        
        # Save generated code (plot_generator state)
        code_file = self.current_case_dir / "code" / f"{iteration_id}_plot_generator.py"
        self._save_plot_generator_code(plot_generator, code_file)
        saved_artifacts["plot_generator_code"] = str(code_file)
        
        # Save stock service state
        service_file = self.current_case_dir / "code" / f"{iteration_id}_stock_service.py"
        self._save_stock_service_code(stock_service, service_file)
        saved_artifacts["stock_service_code"] = str(service_file)
        
        # Save feedback
        if feedback:
            feedback_file = self.current_case_dir / "feedback" / f"{iteration_id}_feedback.txt"
            feedback_file.write_text(feedback, encoding='utf-8')
            saved_artifacts["feedback"] = str(feedback_file)
        
        # Save data snapshot
        if stock_data:
            data_file = self.current_case_dir / "data" / f"{iteration_id}_data.json"
            self._save_stock_data(stock_data, data_file)
            saved_artifacts["data"] = str(data_file)
        
        # Save states
        plot_state_file = self.current_case_dir / "states" / f"{iteration_id}_plot_state.json"
        plot_generator.save_state(str(plot_state_file))
        saved_artifacts["plot_state"] = str(plot_state_file)
        
        service_state_file = self.current_case_dir / "states" / f"{iteration_id}_service_state.json"
        stock_service.save_state(str(service_state_file))
        saved_artifacts["service_state"] = str(service_state_file)
        
        # Update metadata
        plot_features = self._get_plot_features(plot_generator)  # CHANGED
        service_caps = getattr(stock_service, "capabilities",
                               getattr(stock_service, "features", {}))  # CHANGED
        iteration_info = {
            "iteration": iteration,
            "type": iteration_type,
            "timestamp": datetime.now().isoformat(),
            "artifacts": saved_artifacts,
            "plot_version": getattr(plot_generator, "version", "?"),
            "service_version": getattr(stock_service, "version", "?"),
            "features": {
                "plot": plot_features,          # CHANGED
                "service": service_caps         # CHANGED
            }
        }
        self.metadata["iterations"].append(iteration_info)
        self._save_metadata()
        
        return saved_artifacts
    
    def _get_plot_features(self, pg) -> dict:
        """Safely return plot feature dict for legacy or new PlotGenerator."""
        if pg is None:
            return {}
        return getattr(pg, "current_features",
                       getattr(pg, "features", {})) or {}
    
    def _save_plot_generator_code(self, plot_generator, code_file):
        """Persist minimal snapshot of plot generator state + code reference."""
        try:
            features = self._get_plot_features(plot_generator)  # CHANGED
            version = getattr(plot_generator, "version", "?")
            out = {
                "version": version,
                "active_features": {k: v for k, v in features.items() if v and v != "default"},
                "all_features": features
            }
            with open(code_file, "w", encoding="utf-8") as f:
                json.dump(out, f, indent=2)
        except Exception as e:
            # Fallback: write error marker (non-fatal)
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(f'{{"error": "failed to serialize plot generator: {e}"}}')
    
    def _save_stock_service_code(self, stock_service: Any, filepath: Path):
        """Generate and save current stock service code"""
        enabled_features = [k for k, v in stock_service.capabilities.items() if v]
        
        code = f'''# Auto-generated StockService v{stock_service.version}
# Generated at: {datetime.now().isoformat()}

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, List

class StockServiceV{stock_service.version}:
    """Stock service with evolved capabilities"""
    
    def __init__(self):
        self.version = {stock_service.version}
        self.capabilities = {json.dumps(stock_service.capabilities, indent=8)}
    
    def get_stock_prices(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Fetch stock data with enhanced features"""
        # Enabled capabilities: {', '.join(enabled_features)}
        
        data = {{}}
        for symbol in symbols:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=f"{{datetime.now().year}}-01-01")
'''
        
        # Add capability-specific code
        if stock_service.capabilities.get("moving_averages"):
            code += '''
            # Moving averages
            df['MA20'] = df['Close'].rolling(window=20).mean()
            df['MA50'] = df['Close'].rolling(window=50).mean()
'''
        
        if stock_service.capabilities.get("rsi"):
            code += '''
            # RSI calculation
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
'''
        
        if stock_service.capabilities.get("volatility"):
            code += '''
            # Volatility
            returns = df['Close'].pct_change()
            df['Volatility'] = returns.rolling(window=20).std() * np.sqrt(252)
'''
        
        code += '''
            data[symbol] = df
        return data
'''
        filepath.write_text(code, encoding='utf-8')
    
    def _save_stock_data(self, stock_data: Dict[str, pd.DataFrame], filepath: Path):
        """Save stock data snapshot"""
        data_dict = {}
        for symbol, df in stock_data.items():
            if not df.empty:
                # Save last 5 rows as sample
                sample = df.tail(5).to_dict(orient='records')
                data_dict[symbol] = {
                    "shape": list(df.shape),
                    "columns": list(df.columns),
                    "sample": sample,
                    "date_range": [str(df.index[0]), str(df.index[-1])]
                }
        
        with open(filepath, 'w') as f:
            json.dump(data_dict, f, indent=2, default=str)
    
    def _save_metadata(self):
        """Save case metadata"""
        if self.current_case_dir:
            metadata_file = self.current_case_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
    
    def generate_evolution_report(self) -> str:
        """Generate a markdown report of the evolution"""
        if not self.current_case_dir:
            return "No active case"
        
        report = f"""# Code Evolution Report
## Case: {self.metadata['case_name']}
## Symbols: {', '.join(self.metadata['symbols'])}
## Created: {self.metadata['created_at']}

## Evolution Timeline

"""
        for iteration in self.metadata.get("iterations", []):
            report += f"""
### Iteration {iteration['iteration']} ({iteration['type']})
- **Timestamp**: {iteration['timestamp']}
- **Plot Version**: v{iteration['plot_version']}
- **Service Version**: v{iteration['service_version']}
- **Artifacts**:
"""
            for artifact_type, path in iteration['artifacts'].items():
                report += f"  - {artifact_type}: `{Path(path).name}`\n"
            
            # List enabled features
            plot_features = [k for k, v in iteration['features']['plot'].items() if v and v != "default"]
            service_features = [k for k, v in iteration['features']['service'].items() if v]
            
            if plot_features:
                report += f"- **Plot Features**: {', '.join(plot_features)}\n"
            if service_features:
                report += f"- **Service Capabilities**: {', '.join(service_features)}\n"
        
        report += "\n## Summary\n"
        report += f"- Total Iterations: {len(self.metadata.get('iterations', []))}\n"
        report += f"- Final Plot Version: v{self.metadata['iterations'][-1]['plot_version'] if self.metadata.get('iterations') else 1}\n"
        report += f"- Final Service Version: v{self.metadata['iterations'][-1]['service_version'] if self.metadata.get('iterations') else 1}\n"
        
        # Save report
        report_file = self.current_case_dir / "evolution_report.md"
        report_file.write_text(report, encoding='utf-8')
        
        return report
    
    def list_cases(self) -> List[Dict[str, Any]]:
        """List all available cases"""
        cases = []
        for case_dir in self.base_dir.iterdir():
            if case_dir.is_dir():
                metadata_file = case_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        cases.append({
                            "name": case_dir.name,
                            "created": metadata.get("created_at"),
                            "symbols": metadata.get("symbols"),
                            "iterations": len(metadata.get("iterations", []))
                        })
        return sorted(cases, key=lambda x: x["created"], reverse=True)
