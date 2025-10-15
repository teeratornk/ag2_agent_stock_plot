import streamlit as st
import datetime
from feedback_evaluator import FeedbackEvaluator
from stock_service import StockDataService
from plot_generator import PlotGenerator
from artifacts_manager import ArtifactsManager
from code_generator import CodeGenerator
import os
import shutil  # NEW
from pathlib import Path
import re  # added
import json

# --- new helper: feedback formatter ---
def _normalize_feedback_lines(lines):
    cleaned = []
    seen = set()
    for line in lines:
        if not line:
            continue
        # Strip bullets / whitespace
        line = re.sub(r'^[\-\*\u2022]+\s*', '', line).strip()
        # Fix common concatenations
        line = line.replace(")andax", ") and ax").replace(")and ax", ") and ax")
        line = line.replace("YTD % Change')and", "YTD % Change') and")
        # Compress spaces
        line = re.sub(r'\s{2,}', ' ', line)
        # Capitalize first letter if sentence-like
        if line and not line[0].isupper():
            line = line[0].upper() + line[1:]
        # Remove trailing duplicate punctuation
        line = re.sub(r'([:;,\.\!])\1+$', r'\1', line)
        if line.lower() not in seen:
            seen.add(line.lower())
            cleaned.append(line)
    return cleaned

# --- new helper: version display mapping ---
def _display_version(internal_version: int) -> int:
    """
    Map internal version (starts at 1) to user-facing version count of evolutions.
    Internal v1 = baseline -> display v1
    Internal v2 (after 1 evolve) -> display v2
    If you prefer baseline = v0, change logic accordingly.
    Current request: avoid showing an extra +1 after max turns, so cap by baseline + turns.
    """
    return internal_version  # keep baseline = v1 semantics (simplest)
    # If you want baseline shown as v0 instead, uncomment:
    # return max(0, internal_version - 1)

def _extract_python_code(text: str) -> str:
    """
    Extract first ```python ... ``` block; fallback to any ```...```; else return original.
    """
    if not text:
        return text
    code_block = re.search(r"```python\s+([\s\S]*?)```", text, re.IGNORECASE)
    if not code_block:
        code_block = re.search(r"```([\s\S]*?)```", text)
    return code_block.group(1).strip() if code_block else text.strip()

def _inject_style_fallback(code: str) -> str:
    """
    Wrap first plt.style.use(...) with robust fallback while preserving indentation.
    """
    pattern = r"(?P<indent>^[ \t]*)plt\.style\.use\(([^)]+)\)"
    if re.search(pattern, code, flags=re.MULTILINE):
        def repl(m):
            indent = m.group('indent')
            arg = m.group(2)
            block = (
                f"{indent}try:\n"
                f"{indent}    plt.style.use({arg})\n"
                f"{indent}except OSError:\n"
                f"{indent}    for _s in ['ggplot','classic','default']:\n"
                f"{indent}        try:\n"
                f"{indent}            plt.style.use(_s)\n"
                f"{indent}            break\n"
                f"{indent}        except OSError:\n"
                f"{indent}            pass"
            )
            return block
        code = re.sub(pattern, repl, code, count=1, flags=re.MULTILINE)
    else:
        # Insert after first matplotlib import
        lines = code.splitlines()
        inserted = False
        for i, line in enumerate(lines):
            if ("import matplotlib.pyplot" in line or "from matplotlib" in line) and not inserted:
                lines.insert(
                    i + 1,
                    "try:\n    import matplotlib.pyplot as plt  # ensure plt defined\n"
                    "    for _s in ['ggplot','classic','default']:\n"
                    "        try:\n"
                    "            plt.style.use(_s)\n"
                    "            break\n"
                    "        except OSError:\n"
                    "            pass\n"
                    "except Exception:\n    pass"
                )
                inserted = True
                break
        if not inserted:
            # Prepend as last resort
            lines.insert(0,
                "import matplotlib.pyplot as plt\n"
                "try:\n"
                "    for _s in ['ggplot','classic','default']:\n"
                "        try:\n"
                "            plt.style.use(_s)\n"
                "            break\n"
                "        except OSError:\n"
                "            pass\n"
                "except Exception:\n    pass"
            )
        code = "\n".join(lines)
    return code

def _safe_parse_llm_eval(text: str) -> dict:
    """Extract and parse first JSON object from text; return dict or fallback."""
    if not text:
        return {}
    # Attempt direct parse
    try:
        return json.loads(text)
    except:
        pass
    # Try to isolate JSON braces
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except:
            return {}
    return {}

# --- NEW: unified feature access helpers ---
def _get_feature_dict(pg):
    """Return plot feature dict supporting both legacy 'current_features' and new 'features'."""
    return getattr(pg, "current_features", getattr(pg, "features", {})) or {}

def _get_active_features(pg):
    """Return normalized active feature list (exclude falsy/default)."""
    return [k for k, v in _get_feature_dict(pg).items() if v and v != "default"]
# --- END NEW ---

# --- NEW: safe path existence helper ---
def _safe_exists(p) -> bool:
    from os import PathLike
    return isinstance(p, (str, PathLike)) and bool(p) and os.path.exists(p)
# --- END NEW ---

# --- NEW: clear coding workspace helper ---
def _clear_coding_dir(dir_name: str = "coding"):
    p = Path(dir_name)
    if not p.exists():
        p.mkdir(parents=True, exist_ok=True)
        return
    for item in p.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception:
            pass
# --- END NEW ---

def main():
    st.title("📈 Evolving Stock Analysis with AG2")
    st.markdown("Generate YTD stock plots that evolve based on AI and user feedback")
    
    # Initialize session state
    if "plot_generator" not in st.session_state:
        st.session_state.plot_generator = PlotGenerator()
    if "stock_service" not in st.session_state:
        st.session_state.stock_service = StockDataService()
    if "evaluator" not in st.session_state:
        st.session_state.evaluator = FeedbackEvaluator()
    if "artifacts_manager" not in st.session_state:
        st.session_state.artifacts_manager = ArtifactsManager()
    if "outer_iteration" not in st.session_state:
        st.session_state.outer_iteration = 0
    if "total_iterations" not in st.session_state:
        st.session_state.total_iterations = 0
    if "analysis_started" not in st.session_state:
        st.session_state.analysis_started = False
    if "stock_data" not in st.session_state:
        st.session_state.stock_data = None
    if "current_plot_file" not in st.session_state:
        st.session_state.current_plot_file = None
    if "last_execution_error" not in st.session_state:
        st.session_state.last_execution_error = None
    if "llm_eval_results" not in st.session_state:
        st.session_state.llm_eval_results = []
    if "critic_feedback_window" not in st.session_state:
        st.session_state.critic_feedback_window = []  # rolling list of critic feedback strings
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Add mock mode toggle
        mock_mode = st.checkbox("Mock Mode (No Azure Required)", value=True)
        
        # Case name input - simplified default without date
        case_name = st.text_input(
            "Case Name",
            value="stock_analysis",
            help="Name for this analysis case (timestamp will be added automatically)"
        )
        
        # Stock symbols input
        symbols_input = st.text_input(
            "Stock Symbols (comma-separated)",
            value="NVDA,TSLA",
            help="Enter stock symbols separated by commas"
        )
        
        # Iteration settings
        st.subheader("Iteration Settings")
        max_critic_turns = st.slider(
            "Max Critic Turns (per iteration)",
            min_value=1,
            max_value=5,
            value=3,
            help="Maximum critic feedback rounds per iteration"
        )
        
        max_user_iterations = st.slider(
            "Max User Iterations",
            min_value=1,
            max_value=10,
            value=5,
            help="Maximum user feedback iterations"
        )
        
        # Regeneration settings
        max_regen_attempts = st.slider(
            "Max Regen Attempts (failed code turn)",
            min_value=1, max_value=5, value=2,
            help="Automatic re-generation tries before giving critic feedback"
        )
        
        # Quality settings
        critic_threshold = st.slider(
            "Critic Quality Threshold",
            min_value=0.5,
            max_value=1.0,
            value=0.7,
            step=0.1,
            help="Minimum quality score for critic approval"
        )
        
        # LLM evaluation settings
        enable_llm_eval = st.checkbox("Enable LLM L2 Evaluation", value=True, help="Adds a JSON scoring pass after critic")
        llm_eval_criteria = st.multiselect(
            "LLM Eval Criteria",
            ["accuracy","visual_clarity","feature_completeness","code_quality","overall"],
            default=["accuracy","visual_clarity","feature_completeness","code_quality","overall"],
            help="Controls which metrics are emphasized in evaluator prompt"
        )
        
        # Critic context depth setting
        critic_context_depth = st.slider(
            "Critic Context Depth",
            min_value=1, max_value=10, value=3,
            help="How many past critic feedback items to give the writer agent"
        )
        
        # Display evolution summary
        if st.session_state.plot_generator.version > 1:
            st.subheader("📊 Evolution Summary")
            summary = st.session_state.plot_generator.get_evolution_summary()
            shown_version = _display_version(summary["current_version"])
            st.metric("Current Version", shown_version)
            st.metric("Total Improvements", summary["total_improvements"])
            
            if summary["active_features"]:
                st.write("**Active Features:**")
                for feature, value in summary["active_features"].items():
                    if value:
                        st.write(f"• {feature.replace('_', ' ').title()}")
        
        # Display saved cases
        if st.session_state.artifacts_manager.base_dir.exists():
            cases = st.session_state.artifacts_manager.list_cases()
            if cases:
                st.subheader("📁 Recent Cases")
                for case in cases[:5]:  # Show last 5 cases
                    # Extract just the time part if the name is too long
                    display_name = case['name']
                    if len(display_name) > 35:
                        # Show first part and time
                        parts = display_name.split('_')
                        if len(parts) >= 2:
                            display_name = f"{parts[0]}..._{parts[-1]}"
                    st.text(f"• {display_name} ({case['iterations']} iter)")
        
        # Generate button
        generate_button = st.button("🚀 Start Analysis", type="primary")
        
        # Reset button
        if st.button("🔄 Reset Evolution"):
            st.session_state.plot_generator = PlotGenerator()
            st.session_state.evaluator = FeedbackEvaluator()
            st.session_state.outer_iteration = 0
            st.session_state.total_iterations = 0
            st.rerun()
    
    # Main content area
    if generate_button:
        st.session_state.analysis_started = True
        symbols = [s.strip().upper() for s in symbols_input.split(",")]
        
        if not symbols or not all(symbols):
            st.error("Please enter valid stock symbols")
            return
        
        # Create new case if this is the first iteration
        if st.session_state.outer_iteration == 0:
            # Include symbols in case name for clarity
            full_case_name = f"{case_name}_{'-'.join(symbols)}"
            case_dir = st.session_state.artifacts_manager.create_case(full_case_name, symbols)
            st.info(f"📁 Created case: {case_dir.name}")
        
        # Fetch stock data once
        with st.spinner("Fetching stock data..."):
            try:
                stock_data = st.session_state.stock_service.get_stock_prices(symbols)
                gains = st.session_state.stock_service.calculate_ytd_gains(stock_data)
                st.session_state.stock_data = stock_data  # <-- store for later feedback phase
            except Exception as e:
                st.error(f"Error fetching stock data: {e}")
                return
        
        # Display current gains
        st.subheader("📊 Current YTD Gains")
        cols = st.columns(len(symbols))
        for idx, (symbol, gain) in enumerate(gains.items()):
            with cols[idx]:
                st.metric(symbol, f"{gain:.2f}%", delta=f"{gain:.2f}%")
        
        # Start the two-level feedback loop
        st.session_state.outer_iteration += 1
        st.header(f"🔄 User Iteration {st.session_state.outer_iteration}")
        # Track base version & reset critic turn usage
        st.session_state.base_version = st.session_state.plot_generator.version
        st.session_state.last_critic_turns_used = 0
        
        # Inner loop: Critic feedback iterations
        st.subheader("🤖 AI Critic Feedback Loop")
        
        # Initialize critic_feedback_history outside of conditional blocks
        critic_feedback_history = []
        
        if not mock_mode:
            # Original critic feedback loop with Azure
            from agent_factory import AgentFactory
            
            with st.spinner("Setting up agents..."):
                factory = AgentFactory()
                executor, executor_agent = factory.create_executor()
                critic_agent = factory.create_critic()
            
            # Prepare initial message
            today = datetime.datetime.now().date()
            
            # Include previous user feedback if exists
            if st.session_state.outer_iteration > 1 and "user_feedback" in st.session_state:
                user_feedback_context = f"\n\nUser feedback from previous iteration: {st.session_state.user_feedback}"
            else:
                user_feedback_context = ""
            
            message = f"""Today is {today}.
            Create a plot showing stock gain YTD for {', '.join(symbols)}.
            
            Requirements:
            1. Use yfinance to fetch the data
            2. Calculate percentage gains from start of year
            3. Create a matplotlib plot
            4. Save the figure to 'ytd_stock_gains.png'
            
            Make sure the code is standalone and can be executed independently.
            Do not use st.session_state or any Streamlit-specific features.
            """
            
            # Add feature requirements based on current version
            if st.session_state.plot_generator.version > 1:
                active_features = _get_active_features(st.session_state.plot_generator)  # CHANGED
                if active_features:
                    message += f"\n\nImplement these features in the plot: {', '.join(active_features)}"
            
            for critic_turn in range(max_critic_turns):
                st.write(f"**Critic Turn {critic_turn + 1}/{max_critic_turns}**")
                # --- REPLACED BLOCK: build aggregated critic feedback context ---
                if critic_turn > 0 and st.session_state.critic_feedback_window:
                    # Take last N (depth), newest last for readability
                    recent = st.session_state.critic_feedback_window[-critic_context_depth:]
                    aggregated = "\n\n--- PRIOR CRITIC FEEDBACK ---\n".join(recent)
                else:
                    aggregated = None
                if st.session_state.get("last_execution_error"):
                    aggregated = (aggregated or "") + "\n\nLAST_EXECUTION_ERROR:\n" + st.session_state.last_execution_error[:500]

                writer_agent = factory.create_writer(
                    plot_generator=st.session_state.plot_generator,
                    stock_service=st.session_state.stock_service,
                    user_feedback=st.session_state.get("user_feedback"),
                    critic_feedback=aggregated
                )
                # --- END REPLACED BLOCK ---

                col1, col2 = st.columns(2)
                with col1:
                    # Build writer prompt (concise)
                    base_writer_prompt = (
                        f"Generate improved stock YTD code for symbols {', '.join(symbols)}.\n"
                        f"Requirements:\n- Correct YTD % change from first trading day of year\n"
                        f"- Save figure as ytd_stock_gains.png\n"
                        f"- Implement active features & address feedback\n"
                        f"- Add clear title, legend, labels, grid (if appropriate)\n"
                        f"- No Streamlit usage\n"
                    )
                    last_error_snippet = None
                    execution_success = False
                    plot_generated = False
                    executable_code = ""
                    for regen_attempt in range(1, max_regen_attempts + 1):
                        attempt_prefix = f"[Regen {regen_attempt}/{max_regen_attempts}] " if regen_attempt > 1 else ""
                        dynamic_prompt = base_writer_prompt
                        if last_error_snippet:
                            dynamic_prompt += f"\nPrevious error to fix:\n{last_error_snippet[:600]}\n"
                            dynamic_prompt += "Ensure indentation & try/except blocks are syntactically correct.\n"
                        raw_reply = writer_agent.generate_reply(
                            messages=[{"content": dynamic_prompt, "role": "user"}]
                        )
                        raw_reply = raw_reply if isinstance(raw_reply, str) else str(raw_reply)
                        executable_code = _extract_python_code(raw_reply)
                        if not executable_code or "yfinance" not in executable_code:
                            code_gen = CodeGenerator()
                            executable_code = code_gen.generate_plot_code(
                                symbols,
                                st.session_state.plot_generator,
                                st.session_state.stock_service
                            )
                        executable_code = _inject_style_fallback(executable_code)
                        coding_dir = Path("coding"); coding_dir.mkdir(exist_ok=True)
                        code_file = coding_dir / "plot_script.py"
                        with open(code_file, "w", encoding="utf-8") as f:
                            f.write(executable_code)
                        import subprocess, time
                        start_ts = time.time()
                        result = subprocess.run(
                            ["python", "plot_script.py"],  # run inside coding dir
                            capture_output=True,
                            text=True,
                            cwd=str(coding_dir)  # ensure output saved under coding/
                        )
                        duration = time.time() - start_ts
                        execution_success = result.returncode == 0
                        plot_path_candidate = coding_dir / "ytd_stock_gains.png"
                        plot_generated = plot_path_candidate.exists() and execution_success
                        if execution_success and plot_generated:
                            st.success(f"{attempt_prefix}✓ Code executed successfully ({duration:.2f}s)")
                            if result.stdout:
                                with st.expander(f"{attempt_prefix}Execution Output"):
                                    st.text(result.stdout[:3000])
                            st.success(f"{attempt_prefix}Plot v{_display_version(st.session_state.plot_generator.version)} generated")
                            st.image(str(plot_path_candidate))
                            plot_file = str(plot_path_candidate)
                            st.session_state.last_execution_error = None
                            break
                        else:
                            err_msg = result.stderr or "Unknown error"
                            last_error_snippet = err_msg.strip()
                            st.session_state.last_execution_error = last_error_snippet  # <--- store persisted error
                            st.error(f"{attempt_prefix}Execution failed ({duration:.2f}s, rc={result.returncode})")
                            with st.expander(f"{attempt_prefix}Error Details"):
                                st.text(err_msg[:3000])
                            if regen_attempt == max_regen_attempts:
                                with st.expander(f"{attempt_prefix}Generated Code (Final Failed Attempt)"):
                                    st.code(executable_code, language="python")
                    # If never set plot_file and success False, ensure variable exists
                    if not execution_success:
                        plot_file = None

                with col2:
                    # Get critic feedback based on code and execution
                    with st.spinner("Getting critic feedback..."):
                        # Prepare context for critic
                        active_features = _get_active_features(st.session_state.plot_generator)  # CHANGED
                        
                        critic_context = f"""
Evaluate implementation (turn {critic_turn + 1}):
Symbols: {', '.join(symbols)}
Version: v{st.session_state.plot_generator.version}
Active features: {', '.join(active_features) if active_features else 'basic'}
Execution success: {execution_success}
Regen attempts used: {regen_attempt if 'regen_attempt' in locals() else 1}/{max_regen_attempts}
Plot file: {'FOUND' if plot_generated else 'MISSING'}
Last error (if any): {(last_error_snippet[:400] if last_error_snippet else '<none>')}
Recent user feedback: {st.session_state.get('user_feedback','<none>')[:400]}
Previous critic feedback: {st.session_state.get('last_critic_feedback','<none>')[:400] if critic_turn>0 else '<none>'}
Code (truncated):
{executable_code[:900]}
Stdout/Err (truncated):
{(result.stdout if execution_success else (result.stderr or '') )[:600]}
Provide concise improvement feedback. If fully satisfactory, include 'APPROVED'.
"""
                        critic_result = critic_agent.generate_reply(
                            messages=[{"content": critic_context, "role": "user"}]
                        )

                        critic_feedback = critic_result if isinstance(critic_result, str) else str(critic_result)
                        st.session_state.last_critic_feedback = critic_feedback

                        # --- NEW: maintain rolling window ---
                        st.session_state.critic_feedback_window.append(critic_feedback)
                        # Hard cap window size (store up to 20 for memory safety)
                        if len(st.session_state.critic_feedback_window) > 20:
                            st.session_state.critic_feedback_window = st.session_state.critic_feedback_window[-20:]
                        # --- END NEW ---

                        st.session_state.evaluator.store_feedback(critic_feedback, "critic", critic_turn)
                        critic_feedback_history.append(critic_feedback)
                        
                        # Evaluate feedback
                        quality_score = st.session_state.evaluator.score_quality(critic_feedback)
                        is_approved = st.session_state.evaluator.is_approved(critic_feedback)
                        
                        st.write(f"**Critic Feedback:** {critic_feedback[:220]}{'...' if len(critic_feedback)>220 else ''}")
                        st.write(f"Quality Score: {quality_score:.2f}")

                        # --- NEW: LLM secondary evaluation (L2) ---
                        if enable_llm_eval:
                            try:
                                from agent_factory import AgentFactory as _AF
                                llm_eval_agent = _AF.create_llm_evaluator()
                                criteria_str = ", ".join(llm_eval_criteria) if llm_eval_criteria else "overall"
                                eval_prompt = f"""
Provide JSON evaluation (0-1 floats) for criteria: {criteria_str}.
Context:
Execution success: {execution_success}
Plot generated: {bool(plot_file)}
Critic feedback: {critic_feedback[:600]}
Selected features: {', '.join(active_features) if active_features else 'basic'}
Code snippet:
{executable_code[:800]}
If execution failed, penalize accuracy & overall.
Return ONLY JSON.
"""
                                llm_eval_raw = llm_eval_agent.generate_reply(
                                    messages=[{"content": eval_prompt, "role": "user"}]
                                )
                                llm_eval_raw = llm_eval_raw if isinstance(llm_eval_raw, str) else str(llm_eval_raw)
                                llm_eval_parsed = _safe_parse_llm_eval(llm_eval_raw)
                                st.session_state.llm_eval_results.append({
                                    "turn": critic_turn + 1,
                                    "parsed": llm_eval_parsed,
                                    "raw": llm_eval_raw
                                })
                                if llm_eval_parsed:
                                    with st.expander(f"🔎 LLM Eval (Turn {critic_turn + 1})", expanded=False):
                                        st.json(llm_eval_parsed)
                                else:
                                    st.info("LLM eval returned no valid JSON.")
                            except Exception as _e:
                                st.warning(f"LLM eval failed: {_e}")
                        # --- END NEW ---

                        st.session_state.total_iterations += 1
                        st.session_state.artifacts_manager.save_iteration(
                            iteration=st.session_state.total_iterations,
                            iteration_type="critic",
                            plot_generator=st.session_state.plot_generator,
                            stock_service=st.session_state.stock_service,
                            feedback=critic_feedback,
                            plot_path=plot_file if plot_generated else None,
                            stock_data=stock_data
                        )
                        
                        if is_approved and quality_score >= critic_threshold:
                            st.session_state.last_critic_turns_used = critic_turn + 1
                            st.success(f"✅ Approved after {critic_turn + 1} turn(s) v{_display_version(st.session_state.plot_generator.version)}")
                            break
                        else:
                            st.session_state.plot_generator.evolve(critic_feedback, "critic")
                            st.session_state.stock_service.evolve(critic_feedback)
                            st.session_state.last_critic_turns_used = critic_turn + 1
                            st.info(f"Evolved -> v{_display_version(st.session_state.plot_generator.version)} (turn {critic_turn + 1}/{max_critic_turns})")
        else:
            # Mock mode - no Azure required
            for critic_turn in range(max_critic_turns):
                st.write(f"**Critic Turn {critic_turn + 1}/{max_critic_turns}**")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Generate plot directly using plot generator
                    try:
                        plot_file = st.session_state.plot_generator.plot_stock_prices(
                            stock_data,
                            "coding/ytd_stock_gains.png"
                        )
                        st.success(
                            f"Plot {_display_version(st.session_state.plot_generator.version)} "
                            f"generated: {os.path.basename(plot_file)}"
                        )
                    except Exception as e:
                        st.error(f"Error generating plot: {e}")
                        continue
                
                with col2:
                    # Mock critic feedback based on version
                    feedback_templates = [
                        "The plot needs moving averages for better trend visibility. Add 20-day and 50-day MA.",
                        "Good progress! Now add volume analysis in a subplot below the main chart.",
                        "Excellent! The plot is clear and informative. APPROVED"
                    ]
                    
                    critic_feedback = feedback_templates[min(critic_turn, len(feedback_templates)-1)]
                    
                    # Store and evaluate feedback
                    st.session_state.evaluator.store_feedback(
                        critic_feedback, "critic", critic_turn
                    )
                    critic_feedback_history.append(critic_feedback)
                    
                    quality_score = st.session_state.evaluator.score_quality(critic_feedback)
                    is_approved = st.session_state.evaluator.is_approved(critic_feedback)
                    
                    st.write(f"**Critic Feedback:** {critic_feedback}")
                    st.write(f"Quality Score: {quality_score:.2f}")
                    
                    # Save artifacts for this iteration
                    st.session_state.total_iterations += 1
                    artifacts = st.session_state.artifacts_manager.save_iteration(
                        iteration=st.session_state.total_iterations,
                        iteration_type="critic",
                        plot_generator=st.session_state.plot_generator,
                        stock_service=st.session_state.stock_service,
                        feedback=critic_feedback,
                        plot_path=plot_file if 'plot_file' in locals() else None,
                        stock_data=stock_data
                    )
                    
                    # Fixed logic: Require BOTH approval AND meeting threshold
                    # Or just meeting a high threshold even without explicit approval
                    meets_criteria = (is_approved and quality_score >= critic_threshold) or (quality_score >= 0.9)
                    
                    if meets_criteria:
                        st.session_state.last_critic_turns_used = critic_turn + 1
                        st.success(
                            f"✅ Plot approved by critic after {critic_turn + 1} turn(s). "
                            f"Version: v{_display_version(st.session_state.plot_generator.version)} "
                            f"(Score: {quality_score:.2f} ≥ {critic_threshold})"
                        )
                        break
                    else:
                        # Show why it wasn't approved
                        if is_approved and quality_score < critic_threshold:
                            st.warning(f"⚠️ Critic said approved but quality score ({quality_score:.2f}) is below threshold ({critic_threshold})")
                        elif quality_score >= critic_threshold and not is_approved:
                            st.info(f"ℹ️ Quality score meets threshold but critic wants improvements")
                        else:
                            st.info(f"📈 Quality score: {quality_score:.2f} / {critic_threshold} - Continuing improvements")
                        
                        # Evolve both services
                        st.session_state.plot_generator.evolve(critic_feedback, "critic")
                        st.session_state.stock_service.evolve(critic_feedback)
                        st.session_state.last_critic_turns_used = critic_turn + 1
                        turns_used = critic_turn + 1
                        st.info(
                            f"Services evolved -> version v{_display_version(st.session_state.plot_generator.version)} "
                            f"(critic turns used: {turns_used}/{max_critic_turns})"
                        )
        
        # Display final plot from critic loop
        # Use the actual filename returned by plot_stock_prices
        if 'plot_file' in locals() and _safe_exists(plot_file):  # CHANGED
            st.session_state.current_plot_file = plot_file
            st.subheader("📈 Current Plot Version")
            st.image(plot_file, caption=f"Version v{_display_version(st.session_state.plot_generator.version)}")
        elif st.session_state.plot_generator.plot_history:
            latest_plot = st.session_state.plot_generator.plot_history[-1]['filename']
            if _safe_exists(latest_plot):  # CHANGED
                st.session_state.current_plot_file = latest_plot
                st.subheader("📈 Current Plot Version")
                st.image(latest_plot, caption=f"Version v{_display_version(st.session_state.plot_generator.version)}")
        
        # Display critic feedback summary
        with st.expander("📝 Critic Feedback Summary"):
            trends = st.session_state.evaluator.get_feedback_trends()
            if trends:
                st.write(f"**Average Score:** {trends.get('average_score', 0):.2f}")
                st.write(f"**Score Trend:** {trends.get('score_trend', 'N/A')}")
                st.write(f"**Most Common Category:** {trends.get('most_common_category', 'N/A')}")
            # --- NEW: Aggregate LLM eval section ---
            if enable_llm_eval and st.session_state.llm_eval_results:
                st.markdown("### 🔎 LLM Evaluation (Latest)")
                latest_eval = st.session_state.llm_eval_results[-1]["parsed"]
                if latest_eval:
                    cols = st.columns(min(5, len(latest_eval.keys())))
                    numeric_keys = [k for k,v in latest_eval.items() if isinstance(v,(int,float))]
                    for i,k in enumerate(numeric_keys):
                        with cols[i % len(cols)]:
                            st.metric(k.replace("_"," ").title(), f"{latest_eval[k]:.2f}")
                    with st.expander("Full Latest LLM Eval JSON"):
                        st.json(latest_eval)
                if len(st.session_state.llm_eval_results) > 1:
                    with st.expander("LLM Eval History (parsed)"):
                        history = [
                            {
                                "turn": r["turn"],
                                **{k: v for k, v in r["parsed"].items() if isinstance(v,(int,float))}
                            }
                            for r in st.session_state.llm_eval_results if r["parsed"]
                        ]
                        st.dataframe(history)
            # --- END NEW ---
            # Show improvement plan
            if critic_feedback_history:
                plan = st.session_state.evaluator.generate_improvement_plan(critic_feedback_history)
                # --- replaced block: structured + normalized output ---
                st.markdown("### 🔍 Structured Improvement Plan")
                for priority, items in plan.items():
                    if not items:
                        continue
                    label = priority.replace('_', ' ').title()
                    norm_items = _normalize_feedback_lines(items)
                    st.markdown(f"**{label}**")
                    st.markdown("\n".join(f"- {it}" for it in norm_items))
                # Flat normalized list (aggregate view)
                all_items = [i for items in plan.values() for i in items]
                if all_items:
                    st.markdown("### 📌 Consolidated Action Items")
                    consolidated = _normalize_feedback_lines(all_items)
                    st.markdown("\n".join(f"- {it}" for it in consolidated))
                # Raw (optional)
                with st.expander("Raw Plan Data"):
                    st.json(plan)
    # --- Persistent User Feedback Section (shown after at least one iteration) ---
    if st.session_state.outer_iteration > 0:
        st.subheader("👤 User Feedback")
        # Radio persists independently of button state
        user_satisfied = st.radio(
            "Are you satisfied with the current plot?",
            ["Yes, looks great!", "No, needs improvement", "Getting better, but not there yet"],
            key=f"satisfaction_{st.session_state.outer_iteration}",
            index=0
        )

        current_plot_file = st.session_state.get("current_plot_file")
        stock_data = st.session_state.get("stock_data")

        if current_plot_file and os.path.exists(current_plot_file):
            st.image(current_plot_file, caption=f"Current Plot (v{_display_version(st.session_state.plot_generator.version)})")

        if user_satisfied == "Yes, looks great!":
            st.success("🎉 Great! The plot evolution is complete!")
            # Generate evolution report
            report = st.session_state.artifacts_manager.generate_evolution_report()
            
            # Final summary
            with st.expander("📊 Final Evolution Summary"):
                summary = st.session_state.plot_generator.get_evolution_summary()
                st.json(summary)
                
                # Show evolution report
                st.markdown("### 📝 Evolution Report")
                st.markdown(report)
                
                # Show saved artifacts location
                if st.session_state.artifacts_manager.current_case_dir:
                    st.info(f"📁 Artifacts saved to: {st.session_state.artifacts_manager.current_case_dir}")
        else:
            st.info("Let's improve the plot based on your feedback!")
            simple_feedback = st.text_area(
                "Describe what needs improvement:",
                placeholder="e.g., Add volume data; use clearer colors; include moving averages",
                key=f"simple_feedback_{st.session_state.outer_iteration}",
                height=100
            )
            with st.expander("📋 Advanced Feedback Options", expanded=False):
                feedback_type = st.radio(
                    "Choose feedback method:",
                    ["Quick Text", "Guided Questions", "Checkboxes", "Combined"],
                    key=f"feedback_type_{st.session_state.outer_iteration}"
                )
                user_feedback_parts = []
                if feedback_type in ["Guided Questions", "Combined"]:
                    st.write("**🎯 Answer these questions:**")
                    q1 = st.text_input("1. First impression?", key=f"q1_{st.session_state.outer_iteration}")
                    if q1: user_feedback_parts.append(f"First impression: {q1}")
                    q2 = st.text_input("2. Missing data?", key=f"q2_{st.session_state.outer_iteration}")
                    if q2: user_feedback_parts.append(f"Missing: {q2}")
                    q3 = st.text_input("3. Visual improvements?", key=f"q3_{st.session_state.outer_iteration}")
                    if q3: user_feedback_parts.append(f"Visual: {q3}")
                if feedback_type in ["Checkboxes", "Combined"]:
                    st.write("**☑️ Quick selections:**")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.checkbox("Add Moving Averages", key=f"cb_ma_{st.session_state.outer_iteration}"):
                            user_feedback_parts.append("Add moving averages")
                        if st.checkbox("Add Volume", key=f"cb_vol_{st.session_state.outer_iteration}"):
                            user_feedback_parts.append("Add volume subplot")
                        if st.checkbox("Add Annotations", key=f"cb_ann_{st.session_state.outer_iteration}"):
                            user_feedback_parts.append("Add price annotations")
                    with col2:
                        if st.checkbox("Better Colors", key=f"cb_col_{st.session_state.outer_iteration}"):
                            user_feedback_parts.append("Improve colors")
                        if st.checkbox("Improve Labels", key=f"cb_lab_{st.session_state.outer_iteration}"):
                            user_feedback_parts.append("Better labels")
                        if st.checkbox("Add Grid", key=f"cb_grid_{st.session_state.outer_iteration}"):

                            user_feedback_parts.append("Enhance grid")

            priority = st.select_slider(
                "How important are these changes?",
                options=["Nice to have", "Important", "Critical"],
                value="Important",
                key=f"priority_{st.session_state.outer_iteration}"
            )

            if st.button("📤 Submit Feedback", type="primary", key=f"submit_{st.session_state.outer_iteration}"):
                if not (simple_feedback or user_feedback_parts):
                    st.warning("⚠️ Please provide some feedback before submitting")
                else:
                    final_feedback = f"[Priority: {priority}]\n\n"
                    if simple_feedback:
                        final_feedback += f"User request: {simple_feedback}\n\n"
                    if user_feedback_parts:
                        final_feedback += "Additional details:\n" + "\n".join(f"• {p}" for p in user_feedback_parts)
                    st.session_state.user_feedback = final_feedback
                    st.session_state.evaluator.store_feedback(final_feedback, "user", st.session_state.outer_iteration)
                    st.session_state.plot_generator.evolve(final_feedback, "user")
                    st.session_state.stock_service.evolve(final_feedback)
                    st.session_state.total_iterations += 1
                    current_plot_for_artifacts = current_plot_file
                    if not current_plot_for_artifacts and st.session_state.plot_generator.plot_history:
                        current_plot_for_artifacts = st.session_state.plot_generator.plot_history[-1]['filename']
                    if stock_data is not None:
                        st.session_state.artifacts_manager.save_iteration(
                            iteration=st.session_state.total_iterations,
                            iteration_type="user",
                            plot_generator=st.session_state.plot_generator,
                            stock_service=st.session_state.stock_service,
                            feedback=final_feedback,
                            plot_path=current_plot_for_artifacts,
                            stock_data=stock_data
                        )
                    st.success(f"✅ Feedback received! Services evolved to v{st.session_state.plot_generator.version}")
                    with st.expander("📋 Feedback Processed", expanded=True):
                        st.text(final_feedback)
                    st.info("👉 Click 'Start Analysis' again to run the next evolution cycle.")
                    st.session_state.plot_generator.save_state("coding/plot_state.json")

                    # --- NEW: Critic evaluation after user feedback (non-mock mode) ---
                    if not mock_mode:
                        try:
                            from agent_factory import AgentFactory
                            factory = AgentFactory()
                            post_critic = factory.create_critic()
                            active_features = _get_active_features(st.session_state.plot_generator)  # CHANGED
                            post_context = f"""
Evaluate newly applied USER feedback changes.

Version: v{st.session_state.plot_generator.version}
Active features now: {', '.join(active_features) if active_features else 'basic'}
User feedback just applied:
{final_feedback[:1200]}

Assess:
1. Does feedback align with prior critic guidance?
2. Any missing high-impact enhancements?
3. Next concrete step (one sentence) unless complete.

If no further improvements strongly needed, include token: USER_FEEDBACK_OK
Provide concise response."""
                            post_reply = post_critic.generate_reply(
                                messages=[{"content": post_context, "role": "user"}]
                            )
                            post_reply_text = post_reply if isinstance(post_reply, str) else str(post_reply)
                            st.session_state.last_critic_feedback = post_reply_text
                            st.session_state.evaluator.store_feedback(
                                post_reply_text, "critic_post_user", st.session_state.outer_iteration
                            )
                            # Save as its own iteration artifact
                            st.session_state.total_iterations += 1
                            st.session_state.artifacts_manager.save_iteration(
                                iteration=st.session_state.total_iterations,
                                iteration_type="critic_post_user",
                                plot_generator=st.session_state.plot_generator,
                                stock_service=st.session_state.stock_service,
                                feedback=post_reply_text,
                                plot_path=current_plot_for_artifacts,
                                stock_data=stock_data
                            )
                            with st.expander("🤖 Critic Evaluation Of User Feedback", expanded=True):
                                st.write(post_reply_text)
                        except Exception as e:
                            st.warning(f"Post-feedback critic evaluation failed: {e}")
                    # --- END NEW ---
    # Option to view all plot versions
    if st.session_state.plot_generator.version > 1:
        with st.expander("🖼️ View All Plot Versions"):
            cols = st.columns(3)
            for idx, entry in enumerate(st.session_state.plot_generator.plot_history[-6:]):
                with cols[idx % 3]:
                    if os.path.exists(entry['filename']):
                        # Display mapped version
                        display_v = _display_version(entry['version'])
                        st.image(entry['filename'],
                                 caption=f"Version v{display_v}: {os.path.basename(entry['filename'])}")

            # Add download artifacts button
            if st.session_state.artifacts_manager.current_case_dir:
                st.download_button(
                    label="📥 Download Evolution Report",
                    data=st.session_state.artifacts_manager.generate_evolution_report(),
                    file_name=f"{case_name}_evolution_report.md",
                    mime="text/markdown"
                )


if __name__ == "__main__":
    # Create necessary directories
    Path("coding").mkdir(exist_ok=True)
    Path("artifacts").mkdir(exist_ok=True)
    main()
