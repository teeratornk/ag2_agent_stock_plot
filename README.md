## Evolution Teaser (Stock Example Progressive Plot Versions)
These images show one concrete domain (YTD stock performance) used to demonstrate the multi‑agent evolutionary loop (writer → executor → critic → user feedback → refinement). The same loop can evolve any plotting or data‑mining pipeline.

| Version | Preview |
|---------|---------|
| v001 | ![v001 Critic Plot](assets/v001_critic_plot.png) |
| v004 | ![v004 Critic Plot](assets/v004_user_plot.png) |
| v007 | ![v007 Critic Plot](assets/v007_critic_plot.png) |
| v010 | ![v010 Critic Plot](assets/v010_critic_plot.png) |
| v012 | ![v012 Critic Plot](assets/v012_critic_plot.png) |

<p align="center">
  <img src="assets/v001_critic_plot.png" width="30%" />
  <img src="assets/v004_user_plot.png" width="30%" />
  <img src="assets/v007_critic_plot.png" width="30%" /><br/>
  <img src="assets/v010_critic_plot.png" width="30%" />
  <img src="assets/v012_critic_plot.png" width="30%" />
</p>

> This evolution: baseline → add moving averages → volume & annotations → refinement & clarity.

# Multi-Agent Evolution Framework (Stock YTD Example Included)

A domain‑agnostic framework where autonomous agents iteratively generate, execute, critique, and improve code artifacts (plotting scripts, data extraction/mining modules) with optional human steering. The stock YTD plotting system is one packaged example; the architecture supports any structured data → transform → visualize workflow.

---

## Framework Overview (Domain-Agnostic)
Stage | Role | Artifact
------|------|---------
Generation | Writer Agent / Fallback Generator | New or revised code (plot script, data miner, feature calculator)
Execution | Sandboxed Runner | Runtime output (files, logs, metrics, images)
Critique | Critic / Evaluator Agents | Structured feedback, scoring JSON
Adaptation | Evolution Layer | Capability toggles, feature activation, heuristic learning
Human Loop | User Feedback | Higher-level qualitative guidance
Persistence | Artifact Manager | Versioned snapshots, states, diffs, reports

Core Pillars:
- Deterministic fallback path (no LLM required) keeps loop robust.
- Critic reasoning without image pixels (code + run context).
- Pluggable scoring (heuristic + JSON LLM evaluation).
- Feature toggling via feedback keyword inference.
- Longitudinal artifact trail for audit & replay.

---

## Domain-Agnostic Capabilities
Category | Abstraction
---------|------------
Data Acquisition | Any loader (API, file, DB) returning Pandas-like frames
Feature Engineering | Rolling stats, signals, transforms (extensible functions)
Visualization | Multi‑axis, layered plots, subplots, annotations
Evolution Signals | Critic text, user text, execution errors
State Memory | JSON states + incremental feature activation
Evaluation | Heuristic quality + optional secondary model scoring
Artifacts | Code, data samples, rendered outputs, feedback logs, evolution report

---

## Included Example: Stock YTD Module
Implements:
- yfinance ingestion
- YTD % change normalization
- Moving averages, peaks, volume overlay
- Style fallback chain (ggplot → classic → default)
- Iterative enrichment through critic/user prompts

---

## Extending Beyond Stocks
You can plug in:
Use Case | Replace / Add
---------|--------------
Crypto dashboards | Swap data service to ingest exchange APIs
Sensor / IoT streams | Rolling anomaly detection + temporal plots
Marketing KPIs | Multi‑metric composite visualization evolution
LLM evaluation metrics | Latency, quality score distributions
Geospatial heatmaps | Add geo fetch + map rendering layer

---

## How to Add a New Domain Quickly
1. Duplicate stock_service.py → your_domain_service.py (implement get_data() returning dict[str, DataFrame]).
2. Add capability flags (e.g., "outliers", "seasonality", "clustering").
3. Extend evolution keyword map for those flags.
4. Create a minimal plot_generator variant or reuse existing with new feature names.
5. Adjust writer agent system message to mention new feature labels.
6. Run in mock mode first; confirm artifact capture.
7. Introduce domain-specific evaluator (optional) for richer scoring.

---

## Agent Loop Lifecycle (Generalized)
1. Gather active capabilities + recent feedback window.
2. Writer emits standalone script (always runnable cold).
3. Executor runs script in isolated folder (cleared per session).
4. On failure: capture stderr → regeneration attempts.
5. Critic evaluates code + run context; may APPROVE or suggest improvements.
6. Evolution layer toggles features / increments versions.
7. User feedback optionally broadens direction (visual clarity, analytics depth).
8. Artifact manager commits iteration (code, plot/data samples, states, feedback).
9. Report synthesizes timeline.

---

## Evolution Signals Interpreted
Signal Type | Example Phrase | Result
------------|----------------|-------
Critic | "Add moving averages" | Activate moving_avg
User | "Need clearer color contrast" | Future: color palette feature slot
Error | "KeyError: Volume" | Auto-prompts safer volume handling
Approval | "APPROVED" | Stops critic loop (unless user continues)

---

## Design Principles
- Idempotent scripts: each generation yields a self-contained file (no cross-run hidden state).
- Minimal baseline classes (seed objects) encourage emergent complexity rather than premature abstraction.
- Safe fallbacks: style application, missing columns, empty frames.
- Artifact-first: every iteration is auditable & reproducible.

---

## Evolving Stock Analysis (Agentic YTD Plot Generator)

AI‑driven iterative system that generates, executes, critiques, and improves year‑to‑date (YTD) stock performance plots using autonomous agent loops plus user feedback.

## Core Idea
1. Fetch YTD price data (yfinance).
2. Generate standalone Python plotting script (writer agent or fallback generator).
3. Execute script in isolated working directory (`coding/`).
4. Auto‑regenerate on execution failure (configurable retries).
5. Critic agent evaluates code & output context (without seeing the image directly).
6. System evolves internal feature sets (plot + data service).
7. User supplies higher‑level feedback; optional post‑feedback critic pass.
8. All iterations versioned & archived under `artifacts/<case_timestamp>/`.

---

## Key Features
- Dual feedback loops: AI critic + human user.
- Auto regeneration on failure with error‑aware prompts.
- Incremental evolution of:
  - Plot features: moving averages, volume subplot, annotations, peak highlights, style, colors, trend hints.
  - Data capabilities: technical indicators, volatility, RSI, MACD, risk metrics, correlation, benchmark comparison.
- Execution sandbox (`coding/`) with controlled working directory.
- Style fallback injection (prevents invalid matplotlib style crashes).
- Artifact capture: code snapshots, states, feedback, plots, data samples, evolution report.
- Post‑user‑feedback critic evaluation (`critic_post_user` entries).
- Normalized structured improvement plan display.
- Version awareness + history browsing.

---

## Architecture Overview
Component | Purpose
----------|--------
`app.py` | Streamlit UI + orchestration of loops
`agent_factory.py` | Factory for writer / critic / execution / evaluation agents
`plot_generator.py` | Stateful plot evolution engine
`stock_service.py` | Stateful data enrichment service
`code_generator.py` | Deterministic fallback code generator (non‑LLM)
`artifacts_manager.py` | Case & iteration persistence
`feedback_evaluator.py` | Scoring, trends, categorization (not shown here)
`config.py` | Azure/OpenAI model selection & LLM config

Execution Flow (non‑mock):
writer agent → code file → run (subprocess) → (auto-retry if fail) → critic agent → evolve (if not approved) → repeat until approved or max turns → user feedback → optional post‑user critic.

---

## Directory Structure (runtime)
```
stock/
  app.py
  agent_factory.py
  plot_generator.py
  stock_service.py
  code_generator.py
  artifacts_manager.py
  feedback_evaluator.py
  config.py
  coding/                # transient execution outputs (plot_script.py, ytd_stock_gains.png, state)
  artifacts/
    <case_timestamp>/
      plots/
      code/
      feedback/
      data/
      states/
      evolution_report.md
```

---

## Versioning Semantics
- Plot & data service each maintain an internal `version` (start at 1).
- Each evolution (critic or user) increments corresponding version.
- Displayed version mirrors internal (baseline v1).

---

## Iteration Workflow
1. User clicks “Start Analysis”.
2. Critic loop (up to Max Critic Turns):
   - Generate code (LLM or fallback).
   - Auto‑regenerate (Max Regen Attempts) until execution success or attempts exhausted.
   - Critic evaluates final attempt; may mark APPROVED.
   - On non‑approval: evolve + restart turn.
3. User feedback phase:
   - If satisfied → finalize & report.
   - If not → capture feedback, evolve, store artifacts, optional post‑feedback critic.

---

## Mock Mode vs Azure Mode
Mode | Writer | Critic | Regeneration | Post-user critic
-----|--------|--------|--------------|-----------------
Mock (default) | Internal fallback plotting | Template strings | No (simple evolution) | Not invoked
Azure (uncheck Mock) | LLM writer agent | LLM critic agent | Yes | Yes

If you do not configure Azure variables, keep Mock Mode ON.

---

## Environment Configuration (.env)
```
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_API_VERSION=2024-XX-XX
AZURE_OPENAI_ENDPOINT=https://<your-endpoint>.openai.azure.com
AZURE_OPENAI_MODEL=gpt-4o-mini   # or deployment name
AZURE_OPENAI_CODE_WRITER=...
AZURE_OPENAI_CODE_CRITIC=...
AZURE_OPENAI_CODE_EXE=...
```
If unset, app falls back to defaults; Mock Mode avoids remote calls.

---

## Quick Start
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt  # create if missing
streamlit run app.py
```
Optional `requirements.txt`:
```
streamlit
yfinance
matplotlib
pandas
numpy
python-dotenv
```

---

## UI Controls
Sidebar:
- Mock Mode: toggle agentic LLM usage.
- Symbols: comma list (e.g., NVDA,TSLA,MSFT).
- Max Critic Turns: upper bound of critic refinement passes.
- Max Regen Attempts: internal code retry per critic turn (on execution failure).
- Critic Quality Threshold: minimal quality score + approval token.
- Reset Evolution: clears session state.

Main:
- Critic loop details per turn.
- Structured critic improvement plan.
- User feedback composer (quick text, guided, checkboxes).
- Versioned plot gallery.

---

## Auto-Regeneration Logic
Condition | Action
----------|-------
Execution fails (rc != 0) | Capture stderr snippet, augment next writer prompt
Retry count < Max Regen Attempts | Regenerate code
Final attempt still failing | Send failing code + error to critic

Critic sees: success flag, attempts used, last error snippet.

---

## Artifacts & Case Management
Saved per iteration:
- Plot image
- Generated code snapshots (auto-generated “V” classes for traceability)
- Service state & plot state JSON
- Feedback text (critic, user, post-user critic)
- Data sample (shape + last 5 rows)
- Evolution report (markdown) cumulative

Case naming: `<case_name>_YYYYMMDD_HHMMSS`.

---

## Feedback Processing
User feedback triggers:
- Version increment (plot & data service)
- Feature toggles inferred by keyword heuristics
- Optional critic post-evaluation (Azure mode)

Critic approval requires:
1. Presence of 'APPROVED'
2. Quality score ≥ threshold (or high score override in mock logic)

---

## Extensibility Ideas
Add new plot or data feature:
1. Extend `current_features` or `capabilities`.
2. Update `_apply_improvements` / `StockDataService.evolve`.
3. Adjust writer agent system message to mention new feature.
4. Update improvement plan categorization (feedback evaluator).

Swap LLM provider:
- Adjust `config.py` `_build_single_entry`.
- Provide deployment names matching new models.

Add safety filters:
- Pre-execution static scan to block forbidden imports.
- Execution timeout (already configurable in executor factory).

---

## Troubleshooting
Issue | Cause | Fix
------|-------|----
`FileNotFoundError` for style | Unsupported seaborn style | Fallback injection now handles; ensure code regenerated
No plot generated | Empty data / failed script | Check stderr in “Error Details” expander
Versions jump unexpectedly | Multiple evolutions in one run | Inspect artifacts timeline to confirm cause
Artifacts missing | Case not created | Ensure first “Start Analysis” triggered before feedback
Low quality score despite approval | Heuristic parser mismatch | Adjust evaluator or raise threshold

---

## Safety Considerations
- Code execution is local, unsandboxed: review before enabling untrusted inputs.
- No network restriction beyond yfinance; consider adding allowlist.
- Do not feed secrets via user feedback (stored in artifacts plain text).

---

## Limitations
- Critic does not view actual rendered image—infers quality from code.
- Keyword-based evolution may over-activate features.
- No concurrency handling for multiple sessions writing to same case name.

---

## Roadmap (Suggested)
- True image QA (embed-based or vision model).
- Feature registry + dependency graph.
- Structured semantic diff of iterative code.
- Sandbox (e.g., subprocess resource limits, seccomp).
- Caching layer for price data across cases.
- Pluggable scoring model (LLM JSON evaluator already scaffolded in factory).

---

## Cleaning Up
Remove temporary execution artifacts:
```
rm -rf coding/*.png coding/plot_script.py
```
Archive / prune old cases:
```
find artifacts -maxdepth 1 -type d -mtime +14 -exec rm -rf {} \;
```

---


## Attribution
Built with Streamlit, yfinance, matplotlib, and an agentic loop leveraging Azure/OpenAI (optional).

