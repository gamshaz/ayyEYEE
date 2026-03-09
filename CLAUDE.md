# Paper Trading Simulator — ayyEYEE

Bloomberg terminal-style paper trading simulator built with Streamlit for an IE MIF Deep Learning class competition.

## Quick Start

```bash
py -m streamlit run app.py
```

Use `py` on this machine (Windows, Python 3.10.2). Never use `python` or `python3`.

## Architecture

Multi-agent system managing a $1,000,000 paper portfolio across 16 ETFs spanning 4 macro axes (Defensive/Cyclical x Growth/Value x High/Low Beta x US/EM).

### Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit Bloomberg terminal UI (4 tabs) |
| `database.py` | SQLite schema + CRUD (`finance_game.db`) |
| `data_utils.py` | yfinance price data + FRED macro indicators |
| `macro_agent.py` | Claude API strategic allocation (Phase 1 + Phase 2) |
| `tactical_agent.py` | Tactical signals — **placeholder, signals stubbed with TODOs** |
| `risk_agent.py` | Risk checks: 40% position cap, no shorts, 3 trades/day max |
| `execution_agent.py` | Trade execution, cost basis tracking, daily snapshots |
| `export_macro_data.py` | Exports FRED data + generates `claude_prompt.txt` for manual workflow |
| `apply_manual_analysis.py` | Applies Claude desktop JSON response into DB and initializes positions |

### ETF Universe (16 buckets)

```
Axis format: [D/C][G/V][H/L][U/E]

DGHU=XBI   DGHE=EMQQ  DGLU=XLV   DGLE=INDA
DVHU=SDY   DVHE=EELV  DVLU=SPLV  DVLE=EELV
CGHU=SMH   CGHE=EEM   CGLU=RSP   CGLE=CQQQ
CVHU=XLE   CVHE=AVES  CVLU=XLI   CVLE=FEMS
```

## Constraints (Hard Rules)

- **No short selling**
- **Max 40% in any single position**
- **Max 3 trades per day**
- **Sub-strategy max 70%** (each of D/C/G/V/H/L/U/E)
- **Never peek at future prices** — all decisions use data available at the time

## Manual Macro Workflow (No API Credits)

The project currently uses a manual Claude desktop workflow instead of the Anthropic API:

1. `py export_macro_data.py` — fetches FRED indicators, creates `claude_prompt.txt`
2. Paste `claude_prompt.txt` into Claude desktop, get JSON allocation back
3. Paste JSON into `apply_manual_analysis.py` and run it
4. Refresh the Streamlit app

## Current Macro Regime

Late-cycle environment (as of Jan 2026 initialization). Strategy favors **Defensive / Value / Low Beta / US** exposures.

## What's Next

- Implement tactical agent signals (MA crossover, RSI, momentum) in `tactical_agent.py`
- Build rebalancing logic when positions drift from target allocation

## Dependencies

See `requirements.txt`: streamlit, yfinance, fredapi, anthropic, plotly, pandas, python-dotenv.

## Data Files (gitignored)

- `finance_game.db` — SQLite database with portfolio state
- `.env` — API keys (FRED, Anthropic)
