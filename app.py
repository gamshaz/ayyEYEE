"""
app.py - Bloomberg Terminal Style Streamlit UI
Paper Trading Simulator — $1,000,000 USD portfolio
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

import database as db
import data_utils
import macro_agent
import tactical_agent
import risk_agent
import execution_agent

# ─── Page config (MUST be first Streamlit call) ───────────────────────────────
st.set_page_config(
    page_title="BLOOMBERG TERMINAL — PAPER TRADING SIM",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Bloomberg Terminal CSS ───────────────────────────────────────────────────
BLOOMBERG_CSS = """
<style>
/* ── Global reset & font ── */
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');

html, body, [class*="css"], .stApp, .block-container,
div, p, span, label, button, input, select, textarea, th, td, li {
    font-family: 'Courier New', 'Share Tech Mono', monospace !important;
}

/* ── Background ── */
.stApp { background-color: #0a0a0a !important; }
.block-container { background-color: #0a0a0a !important; padding-top: 1rem !important; }
section[data-testid="stSidebar"] { background-color: #0d0d0d !important; border-right: 1px solid #ffb000; }

/* ── Text colors ── */
body, .stMarkdown, p, span, label, div { color: #00ff41 !important; }
h1, h2, h3, h4, h5, h6 { color: #ffb000 !important; text-transform: uppercase; letter-spacing: 2px; }
.stMetric label { color: #008f11 !important; font-size: 0.75rem !important; text-transform: uppercase; }
.stMetric [data-testid="stMetricValue"] { color: #00ff41 !important; }
.stMetric [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ── Buttons ── */
.stButton > button {
    background-color: #0a0a0a !important;
    color: #ffb000 !important;
    border: 1px solid #ffb000 !important;
    border-radius: 0 !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 0.4rem 1.2rem !important;
    transition: all 0.1s ease !important;
}
.stButton > button:hover {
    background-color: #ffb000 !important;
    color: #0a0a0a !important;
}
.stButton > button:active {
    background-color: #ff6600 !important;
    color: #0a0a0a !important;
}

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #0a0a0a !important;
    border-bottom: 1px solid #ffb000 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    color: #008f11 !important;
    background-color: #0a0a0a !important;
    border: 1px solid #1a1a1a !important;
    border-radius: 0 !important;
    font-family: 'Courier New', monospace !important;
    font-size: 0.8rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 0.5rem 1.5rem !important;
}
.stTabs [aria-selected="true"] {
    color: #ffb000 !important;
    background-color: #0d0d0d !important;
    border-bottom: 2px solid #ffb000 !important;
}

/* ── DataFrames / Tables ── */
.stDataFrame, .dataframe { background-color: #050505 !important; }
.stDataFrame thead th {
    background-color: #111 !important;
    color: #ffb000 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    border: 1px solid #333 !important;
}
.stDataFrame tbody td {
    background-color: #080808 !important;
    color: #00ff41 !important;
    border: 1px solid #1a1a1a !important;
    font-size: 0.78rem !important;
}

/* ── Input fields ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background-color: #050505 !important;
    color: #00ff41 !important;
    border: 1px solid #333 !important;
    border-radius: 0 !important;
    font-family: 'Courier New', monospace !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #050505; }
::-webkit-scrollbar-thumb { background: #333; border-radius: 0; }

/* ── Success / warning / error overrides ── */
.stAlert { border-radius: 0 !important; border-left: 3px solid #ffb000 !important; }
div[data-testid="stNotification"] { background-color: #0d0d0d !important; }

/* ── Sidebar text ── */
section[data-testid="stSidebar"] * { color: #00ff41 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #ffb000 !important; }

/* ── Plotly chart backgrounds ── */
.js-plotly-plot .plotly { background: #0a0a0a !important; }
</style>
"""

st.markdown(BLOOMBERG_CSS, unsafe_allow_html=True)


# ─── Session state initialization ─────────────────────────────────────────────
def init_session():
    # Initializes all session state variables to defaults on first run
    defaults = {
        "db_initialized":        False,
        "sim_started":           False,
        "macro_phase1_done":     False,
        "macro_phase1_result":   None,
        "macro_confirmed":       False,
        "macro_phase2_done":     False,
        "macro_full_result":     None,
        "positions_initialized": False,
        "current_date":          "2026-01-02",
        "last_run_time":         None,
        "agent_log":             "",
        "proposed_trades":       [],
        "approved_trades":       [],
        "rejected_trades":       [],
        "prices":                {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session()

# Initialize DB once per session
if not st.session_state.db_initialized:
    db.initialize_db()
    st.session_state.db_initialized = True

# Auto-load existing DB state (e.g. after apply_manual_analysis.py was run)
if not st.session_state.sim_started:
    _state = db.get_simulation_state()
    _alloc = db.get_target_allocation()
    _macro = db.get_macro_log()
    if _state and _alloc:
        st.session_state.sim_started           = True
        st.session_state.positions_initialized = True
        st.session_state.macro_phase1_done     = True
        st.session_state.macro_confirmed       = True
        st.session_state.macro_phase2_done     = True
        st.session_state.current_date          = _state["current_date"]
        # Reconstruct a minimal result dict from DB so Tab 4 renders
        if not st.session_state.macro_full_result:
            summary_rows = [
                {
                    "indicator":      r["indicator"],
                    "key":            r["indicator"],
                    "value":          r["value"] or 0,
                    "unit":           "",
                    "trend":          r["trend"] or "stable",
                    "interpretation": r["interpretation"] or "",
                }
                for r in _macro
            ]
            st.session_state.macro_full_result = {
                "summary_rows":     summary_rows,
                "regime_narrative": next(
                    (r["interpretation"] for r in _macro if len(r.get("interpretation","")) > 100),
                    "Macro analysis loaded from database."
                ),
                "axis_scores": {},
                "allocation":  _alloc,
            }


# ─── Helper: load live portfolio state ────────────────────────────────────────
def load_portfolio_state():
    # Reads current simulation state from DB and returns summary dict
    state    = db.get_simulation_state()
    positions = db.get_positions()
    snapshots = db.get_daily_snapshots()

    cash            = state["cash_balance"] if state else db.INITIAL_CASH
    total_value     = state["total_portfolio_value"] if state else db.INITIAL_CASH
    holdings_value  = total_value - cash

    # Compute daily P&L from snapshots
    daily_pnl       = 0.0
    daily_pnl_pct   = 0.0
    total_return_pct = 0.0
    if len(snapshots) >= 2:
        prev  = snapshots[-2]["total_equity"]
        curr  = snapshots[-1]["total_equity"]
        daily_pnl     = curr - prev
        daily_pnl_pct = (daily_pnl / prev * 100) if prev > 0 else 0.0
    if snapshots:
        first = snapshots[0]["total_equity"]
        total_return_pct = ((total_value - first) / first * 100) if first > 0 else 0.0

    return {
        "cash":             cash,
        "total_value":      total_value,
        "holdings_value":   holdings_value,
        "daily_pnl":        daily_pnl,
        "daily_pnl_pct":    daily_pnl_pct,
        "total_return_pct": total_return_pct,
        "positions":        positions,
        "snapshots":        snapshots,
    }


# ─── Helper: Bloomberg separator ──────────────────────────────────────────────
def bsep(label: str = ""):
    # Renders a Bloomberg-style terminal separator line
    if label:
        st.markdown(
            f'<div style="color:#ffb000;font-family:Courier New,monospace;'
            f'font-size:0.78rem;margin:0.5rem 0;">'
            f'{"═"*4} {label.upper()} {"═"*(max(4, 60-len(label)-6))}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="color:#333;font-family:Courier New,monospace;'
            'font-size:0.78rem;margin:0.4rem 0;">'
            '{"═"*64}</div>',
            unsafe_allow_html=True
        )


def terminal_text(text: str, color: str = "#00ff41", size: str = "0.8rem"):
    # Renders monospace terminal-style text
    st.markdown(
        f'<pre style="color:{color};font-family:Courier New,monospace;'
        f'font-size:{size};background:#050505;padding:0.8rem;'
        f'border:1px solid #1a1a1a;overflow-x:auto;">{text}</pre>',
        unsafe_allow_html=True
    )


# ─── TOP TICKER TAPE ──────────────────────────────────────────────────────────
def render_ticker_tape():
    # Renders the top-of-page Bloomberg-style portfolio metrics bar
    pf = load_portfolio_state()
    tv = pf["total_value"]
    cash = pf["cash"]
    dpnl = pf["daily_pnl"]
    dpct = pf["daily_pnl_pct"]
    tret = pf["total_return_pct"]

    dpnl_color = "#00ff41" if dpnl >= 0 else "#ff3333"
    tret_color = "#00ff41" if tret >= 0 else "#ff3333"
    dpnl_sign  = "+" if dpnl >= 0 else ""
    tret_sign  = "+" if tret >= 0 else ""

    tape_html = f"""
    <div style="
        background:#050505;
        border:1px solid #ffb000;
        border-radius:0;
        padding:0.5rem 1.5rem;
        margin-bottom:1rem;
        font-family:'Courier New',monospace;
        font-size:0.82rem;
        display:flex;
        flex-wrap:wrap;
        gap:2rem;
        align-items:center;
    ">
        <span style="color:#ffb000;font-weight:bold;letter-spacing:1px;">
            ╔══ PAPER TRADING TERMINAL ══╗
        </span>
        <span>
            <span style="color:#008f11;">PORTFOLIO:</span>
            <span style="color:#00ff41;"> ${tv:,.2f}</span>
        </span>
        <span>
            <span style="color:#008f11;">CASH:</span>
            <span style="color:#00d4ff;"> ${cash:,.2f}</span>
        </span>
        <span>
            <span style="color:#008f11;">DAILY P&L:</span>
            <span style="color:{dpnl_color};"> {dpnl_sign}${dpnl:,.2f} ({dpnl_sign}{dpct:.2f}%)</span>
        </span>
        <span>
            <span style="color:#008f11;">TOTAL RETURN:</span>
            <span style="color:{tret_color};"> {tret_sign}{tret:.2f}%</span>
        </span>
        <span>
            <span style="color:#008f11;">SIM DATE:</span>
            <span style="color:#ffb000;"> {st.session_state.current_date}</span>
        </span>
    </div>
    """
    st.markdown(tape_html, unsafe_allow_html=True)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
def render_sidebar():
    # Renders the command panel sidebar with controls and status indicators
    with st.sidebar:
        st.markdown(
            '<div style="color:#ffb000;font-family:Courier New,monospace;'
            'font-size:1rem;font-weight:bold;letter-spacing:2px;border-bottom:'
            '1px solid #ffb000;padding-bottom:0.5rem;margin-bottom:1rem;">'
            '[ COMMAND PANEL ]</div>',
            unsafe_allow_html=True
        )

        # Simulation date display
        st.markdown(
            f'<div style="color:#ffb000;font-family:Courier New,monospace;'
            f'font-size:0.85rem;margin-bottom:0.8rem;">'
            f'SIM DATE: <span style="color:#00d4ff;">{st.session_state.current_date}</span></div>',
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ── INIT PORTFOLIO ──
        if st.button("[ INIT PORTFOLIO ]", key="btn_init", use_container_width=True):
            _handle_init_portfolio()

        # ── CONFIRM MACRO ── (shown only after phase 1 complete, before phase 2)
        if st.session_state.macro_phase1_done and not st.session_state.macro_confirmed:
            st.markdown(
                '<div style="color:#ff6600;font-family:Courier New,monospace;'
                'font-size:0.75rem;margin-top:0.5rem;">'
                '⚠ REVIEW MACRO ANALYSIS IN TAB 4<br>THEN CONFIRM BELOW</div>',
                unsafe_allow_html=True
            )
            feedback_input = st.text_input(
                "Type CONFIRM or provide feedback:",
                key="macro_feedback_input",
                placeholder="CONFIRM"
            )
            if st.button("[ CONFIRM ALLOCATION ]", key="btn_confirm", use_container_width=True):
                _handle_confirm(feedback_input)

        st.markdown("---")

        # ── ADVANCE DAY ──
        if st.button("[ ADVANCE DAY ]", key="btn_advance", use_container_width=True):
            _handle_advance_day()

        # ── RUN AGENTS ──
        if st.button("[ RUN AGENTS ]", key="btn_run_agents", use_container_width=True):
            _handle_run_agents()

        st.markdown("---")

        # ── EXECUTE TRADES ── (appears when there are approved trades pending)
        if st.session_state.approved_trades:
            n = len(st.session_state.approved_trades)
            st.markdown(
                f'<div style="color:#ffb000;font-family:Courier New,monospace;'
                f'font-size:0.75rem;">{n} APPROVED TRADE(S) PENDING</div>',
                unsafe_allow_html=True
            )
            if st.button("[ EXECUTE TRADES ]", key="btn_execute", use_container_width=True):
                _handle_execute_trades()

        st.markdown("---")

        # ── STATUS ──
        status_color = "#00ff41" if st.session_state.sim_started else "#ff6600"
        status_label = "LIVE" if st.session_state.sim_started else "OFFLINE"
        last_run = st.session_state.last_run_time or "—"
        st.markdown(
            f'<div style="font-family:Courier New,monospace;font-size:0.75rem;">'
            f'STATUS: <span style="color:{status_color};">● {status_label}</span><br>'
            f'LAST RUN: <span style="color:#008f11;">{last_run}</span>'
            f'</div>',
            unsafe_allow_html=True
        )

        # ── RESET ──
        st.markdown("---")
        if st.button("[ RESET SIM ]", key="btn_reset", use_container_width=True):
            _handle_reset()


# ─── Sidebar action handlers ───────────────────────────────────────────────────

def _handle_init_portfolio():
    # Runs Phase 1 of the macro agent: fetches FRED data and generates summary
    with st.spinner("FETCHING FRED MACRO DATA..."):
        try:
            indicators = data_utils.get_macro_indicators()
            phase1_result = macro_agent.phase1_analyze(indicators)
            st.session_state.macro_phase1_result = phase1_result
            st.session_state.macro_phase1_done   = True
            st.session_state._raw_indicators     = indicators
            st.session_state.last_run_time = datetime.now().strftime("%H:%M:%S")
            st.success("MACRO ANALYSIS COMPLETE — Review Tab 4 and CONFIRM")
        except Exception as e:
            st.error(f"INIT ERROR: {e}")


def _handle_confirm(feedback: str):
    # Runs Phase 2 after user confirms macro summary: scores axes + allocates
    with st.spinner("RUNNING ALLOCATION ENGINE..."):
        try:
            indicators = st.session_state.get("_raw_indicators", {})
            if not indicators:
                indicators = data_utils.get_macro_indicators()

            phase2_result = macro_agent.phase2_allocate(indicators, feedback=feedback or "CONFIRM")
            phase1_result = st.session_state.macro_phase1_result or {}

            st.session_state.macro_full_result  = {**phase1_result, **phase2_result}
            st.session_state.macro_confirmed     = True
            st.session_state.macro_phase2_done   = True

            # Now initialize positions based on allocation
            with st.spinner("INITIALIZING POSITIONS..."):
                prices = data_utils.get_all_current_prices(st.session_state.current_date)
                st.session_state.prices = prices
                allocation = phase2_result.get("allocation", [])
                if allocation and prices:
                    execution_agent.initialize_positions_from_allocation(
                        allocation, prices, db.INITIAL_CASH, st.session_state.current_date
                    )
                    st.session_state.positions_initialized = True
                    st.session_state.sim_started = True
                    st.session_state.last_run_time = datetime.now().strftime("%H:%M:%S")
                    st.success("PORTFOLIO INITIALIZED — SIMULATION LIVE")
        except Exception as e:
            st.error(f"ALLOCATION ERROR: {e}")


def _handle_advance_day():
    # Advances simulation date by one day (skips weekends)
    current = datetime.strptime(st.session_state.current_date, "%Y-%m-%d")
    next_day = current + timedelta(days=1)
    # Skip Saturday (5) and Sunday (6)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    st.session_state.current_date = next_day.strftime("%Y-%m-%d")

    # Refresh prices for new date
    with st.spinner(f"FETCHING PRICES FOR {st.session_state.current_date}..."):
        try:
            prices = data_utils.get_all_current_prices(st.session_state.current_date)
            st.session_state.prices = prices
            if prices and st.session_state.sim_started:
                execution_agent.refresh_position_prices(prices)
            st.session_state.last_run_time = datetime.now().strftime("%H:%M:%S")
        except Exception as e:
            st.error(f"PRICE FETCH ERROR: {e}")


def _handle_run_agents():
    # Runs tactical + risk agents to generate trade proposals
    if not st.session_state.sim_started:
        st.warning("INITIALIZE PORTFOLIO FIRST")
        return
    with st.spinner("RUNNING TACTICAL AGENT..."):
        try:
            prices    = st.session_state.prices or data_utils.get_all_current_prices(st.session_state.current_date)
            positions = db.get_positions()
            state     = db.get_simulation_state()
            cash      = state["cash_balance"] if state else db.INITIAL_CASH
            pf_value  = state["total_portfolio_value"] if state else db.INITIAL_CASH

            proposed = tactical_agent.propose_trades(
                st.session_state.current_date, positions, prices, pf_value
            )
            approved, rejected = risk_agent.validate_trades(proposed, positions, cash, pf_value, prices)

            st.session_state.proposed_trades = proposed
            st.session_state.approved_trades = approved
            st.session_state.rejected_trades = rejected
            st.session_state.last_run_time   = datetime.now().strftime("%H:%M:%S")

            if approved:
                st.success(f"{len(approved)} TRADE(S) APPROVED — Click EXECUTE TRADES")
            else:
                st.info("NO TRADES PROPOSED TODAY")
        except Exception as e:
            st.error(f"AGENT RUN ERROR: {e}")


def _handle_execute_trades():
    # Executes approved trades and saves daily snapshot
    with st.spinner("EXECUTING TRADES..."):
        try:
            prices    = st.session_state.prices
            positions = db.get_positions()
            state     = db.get_simulation_state()
            cash      = state["cash_balance"] if state else db.INITIAL_CASH

            result = execution_agent.execute_trades(
                st.session_state.approved_trades,
                st.session_state.current_date,
                prices,
                cash,
                positions,
            )

            # Save daily snapshot
            updated_positions = db.get_positions()
            execution_agent.save_daily_snapshot(
                st.session_state.current_date, result["new_cash"], updated_positions, prices
            )

            st.session_state.agent_log      = result["execution_log"]
            st.session_state.approved_trades = []
            st.session_state.proposed_trades = []
            st.session_state.last_run_time   = datetime.now().strftime("%H:%M:%S")
            st.success(f"{len(result['executed_trades'])} TRADE(S) EXECUTED")
        except Exception as e:
            st.error(f"EXECUTION ERROR: {e}")


def _handle_reset():
    # Resets the entire simulation (wipes DB and session state)
    db.reset_db()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# ─── TAB 1: TRADING FLOOR ─────────────────────────────────────────────────────
def render_trading_floor():
    st.markdown(
        '<h3 style="color:#ffb000;letter-spacing:3px;">[ TRADING FLOOR ]</h3>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(
            '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
            '═══ MACRO REGIME ═══</div>',
            unsafe_allow_html=True
        )
        result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")
        if result:
            narrative = result.get("regime_narrative", "—")
            terminal_text(narrative, color="#00d4ff")
        else:
            terminal_text("NO MACRO DATA — RUN [ INIT PORTFOLIO ]", color="#555")

    with col2:
        st.markdown(
            '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
            '═══ PROPOSED TRADES ═══</div>',
            unsafe_allow_html=True
        )
        if st.session_state.proposed_trades:
            df_trades = pd.DataFrame(st.session_state.proposed_trades)
            st.dataframe(df_trades, use_container_width=True, hide_index=True)
        else:
            terminal_text("NO TRADES PROPOSED — RUN [ RUN AGENTS ]", color="#555")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
        '═══ AGENT REASONING LOG ═══</div>',
        unsafe_allow_html=True
    )

    # Combine approved + rejected into one log
    log_lines = []
    if st.session_state.approved_trades:
        log_lines.append("APPROVED TRADES:")
        for t in st.session_state.approved_trades:
            log_lines.append(
                f"  ✓ {t.get('action','?'):4s} {t.get('symbol','?'):6s} "
                f"{t.get('shares',0):8.2f} sh  | {t.get('reason','')}"
            )
    if st.session_state.rejected_trades:
        log_lines.append("\nREJECTED TRADES:")
        for t in st.session_state.rejected_trades:
            log_lines.append(
                f"  ✗ {t.get('action','?'):4s} {t.get('symbol','?'):6s} "
                f"| {t.get('rejection_reason','')}"
            )
    if st.session_state.agent_log:
        log_lines.append("\n" + st.session_state.agent_log)

    log_text = "\n".join(log_lines) if log_lines else "NO LOG ENTRIES"
    terminal_text(log_text)


# ─── TAB 2: PORTFOLIO ─────────────────────────────────────────────────────────
def render_portfolio():
    st.markdown(
        '<h3 style="color:#ffb000;letter-spacing:3px;">[ PORTFOLIO HOLDINGS ]</h3>',
        unsafe_allow_html=True
    )
    positions = db.get_positions()
    prices    = st.session_state.prices

    if not positions:
        terminal_text("NO POSITIONS — INITIALIZE PORTFOLIO FIRST", color="#555")
        return

    rows = []
    total_mv   = 0.0
    total_cost = 0.0
    for pos in positions:
        symbol   = pos["symbol"]
        bucket   = pos["strategy_bucket"]
        shares   = pos["shares"]
        avg_cost = pos["average_cost"]
        cur_px   = prices.get(symbol, pos.get("current_price", 0))
        mv       = shares * cur_px
        cost_basis = shares * avg_cost
        pnl      = mv - cost_basis
        pnl_pct  = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
        total_mv   += mv
        total_cost += cost_basis
        rows.append({
            "BUCKET":    bucket,
            "TICKER":    symbol,
            "SHARES":    f"{shares:,.4f}",
            "AVG COST":  f"${avg_cost:,.4f}",
            "LAST PX":   f"${cur_px:,.4f}",
            "MKT VALUE": f"${mv:,.2f}",
            "P&L":       f"{'+'if pnl>=0 else ''}{pnl:,.2f}",
            "P&L%":      f"{'+'if pnl_pct>=0 else ''}{pnl_pct:.2f}%",
            "_pnl":      pnl,
        })

    # Sort by market value descending
    rows.sort(key=lambda r: float(r["MKT VALUE"].replace("$", "").replace(",", "")), reverse=True)

    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])

    # Style positive/negative P&L
    def color_pnl(val):
        try:
            num = float(str(val).replace("+", "").replace("%", "").replace("$", "").replace(",", ""))
            return "color: #00ff41" if num >= 0 else "color: #ff3333"
        except Exception:
            return ""

    styled = df.style.applymap(color_pnl, subset=["P&L", "P&L%"])
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # Portfolio totals
    total_pnl = total_mv - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    pnl_color = "#00ff41" if total_pnl >= 0 else "#ff3333"

    st.markdown(
        f'<div style="font-family:Courier New,monospace;font-size:0.8rem;'
        f'border-top:1px solid #333;padding-top:0.5rem;margin-top:0.5rem;">'
        f'<span style="color:#ffb000;">TOTAL HOLDINGS:</span> '
        f'<span style="color:#00ff41;">${total_mv:,.2f}</span>'
        f' &nbsp;|&nbsp; '
        f'<span style="color:#ffb000;">TOTAL P&L:</span> '
        f'<span style="color:{pnl_color};">'
        f'{"+" if total_pnl>=0 else ""}${total_pnl:,.2f} '
        f'({"+" if total_pnl_pct>=0 else ""}{total_pnl_pct:.2f}%)'
        f'</span></div>',
        unsafe_allow_html=True
    )

    # Recent transactions
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
        '═══ RECENT TRANSACTIONS ═══</div>',
        unsafe_allow_html=True
    )
    txns = db.get_transactions()[:20]
    if txns:
        df_txns = pd.DataFrame(txns)[["date", "action", "symbol", "shares", "price", "reason"]]
        df_txns["shares"] = df_txns["shares"].map(lambda x: f"{x:,.4f}")
        df_txns["price"]  = df_txns["price"].map(lambda x: f"${x:,.4f}")
        df_txns.columns   = ["DATE", "ACTION", "TICKER", "SHARES", "PRICE", "REASON"]
        st.dataframe(df_txns, use_container_width=True, hide_index=True)
    else:
        terminal_text("NO TRANSACTIONS YET", color="#555")


# ─── TAB 3: PERFORMANCE ───────────────────────────────────────────────────────
def render_performance():
    st.markdown(
        '<h3 style="color:#ffb000;letter-spacing:3px;">[ PERFORMANCE ANALYTICS ]</h3>',
        unsafe_allow_html=True
    )
    snapshots = db.get_daily_snapshots()

    if len(snapshots) < 2:
        terminal_text("INSUFFICIENT DATA — RUN SIMULATION FOR AT LEAST 2 DAYS", color="#555")
        return

    df_snap = pd.DataFrame(snapshots)
    df_snap["date"] = pd.to_datetime(df_snap["date"])
    initial_equity  = df_snap["total_equity"].iloc[0]

    # ── KPI Cards ──
    final_equity   = df_snap["total_equity"].iloc[-1]
    total_return   = (final_equity - initial_equity) / initial_equity * 100
    rolling_max    = df_snap["total_equity"].cummax()
    drawdown       = (df_snap["total_equity"] - rolling_max) / rolling_max * 100
    max_drawdown   = drawdown.min()
    daily_returns  = df_snap["total_equity"].pct_change().dropna()
    sharpe         = (daily_returns.mean() / daily_returns.std() * (252 ** 0.5)) if daily_returns.std() > 0 else 0
    win_rate       = (daily_returns > 0).mean() * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ret_color = "#00ff41" if total_return >= 0 else "#ff3333"
        st.markdown(
            f'<div style="background:#0d0d0d;border:1px solid #333;padding:1rem;text-align:center;">'
            f'<div style="color:#008f11;font-size:0.7rem;">TOTAL RETURN</div>'
            f'<div style="color:{ret_color};font-size:1.3rem;font-weight:bold;">'
            f'{"+"if total_return>=0 else ""}{total_return:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c2:
        dd_color = "#ff3333" if max_drawdown < -5 else "#ffb000"
        st.markdown(
            f'<div style="background:#0d0d0d;border:1px solid #333;padding:1rem;text-align:center;">'
            f'<div style="color:#008f11;font-size:0.7rem;">MAX DRAWDOWN</div>'
            f'<div style="color:{dd_color};font-size:1.3rem;font-weight:bold;">'
            f'{max_drawdown:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c3:
        sh_color = "#00ff41" if sharpe > 1 else ("#ffb000" if sharpe > 0 else "#ff3333")
        st.markdown(
            f'<div style="background:#0d0d0d;border:1px solid #333;padding:1rem;text-align:center;">'
            f'<div style="color:#008f11;font-size:0.7rem;">SHARPE RATIO</div>'
            f'<div style="color:{sh_color};font-size:1.3rem;font-weight:bold;">'
            f'{sharpe:.2f}</div></div>',
            unsafe_allow_html=True
        )
    with c4:
        wr_color = "#00ff41" if win_rate > 50 else "#ff3333"
        st.markdown(
            f'<div style="background:#0d0d0d;border:1px solid #333;padding:1rem;text-align:center;">'
            f'<div style="color:#008f11;font-size:0.7rem;">WIN RATE</div>'
            f'<div style="color:{wr_color};font-size:1.3rem;font-weight:bold;">'
            f'{win_rate:.1f}%</div></div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Equity Curve ──
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_snap["date"],
        y=df_snap["total_equity"],
        mode="lines",
        name="Portfolio Equity",
        line=dict(color="#00ff41", width=2),
        fill="tozeroy",
        fillcolor="rgba(0,255,65,0.05)",
    ))
    fig.add_trace(go.Scatter(
        x=df_snap["date"],
        y=[initial_equity] * len(df_snap),
        mode="lines",
        name="Initial Capital",
        line=dict(color="#ffb000", width=1, dash="dot"),
    ))
    fig.update_layout(
        title=dict(text="EQUITY CURVE", font=dict(color="#ffb000", family="Courier New", size=14)),
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        font=dict(color="#00ff41", family="Courier New"),
        xaxis=dict(gridcolor="#1a1a1a", color="#008f11", showgrid=True),
        yaxis=dict(gridcolor="#1a1a1a", color="#008f11", showgrid=True,
                   tickformat="$,.0f"),
        legend=dict(bgcolor="#050505", bordercolor="#333", font=dict(color="#00ff41")),
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Drawdown chart ──
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df_snap["date"],
        y=drawdown,
        mode="lines",
        name="Drawdown",
        line=dict(color="#ff3333", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(255,51,51,0.08)",
    ))
    fig2.update_layout(
        title=dict(text="DRAWDOWN (%)", font=dict(color="#ffb000", family="Courier New", size=14)),
        paper_bgcolor="#050505",
        plot_bgcolor="#050505",
        font=dict(color="#00ff41", family="Courier New"),
        xaxis=dict(gridcolor="#1a1a1a", color="#008f11"),
        yaxis=dict(gridcolor="#1a1a1a", color="#008f11", tickformat=".2f"),
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Daily snapshots table ──
    st.markdown(
        '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
        '═══ DAILY SNAPSHOTS ═══</div>',
        unsafe_allow_html=True
    )
    df_display = df_snap[["date", "cash", "holdings_value", "total_equity"]].copy()
    df_display["date"]           = df_display["date"].dt.strftime("%Y-%m-%d")
    df_display["cash"]           = df_display["cash"].map(lambda x: f"${x:,.2f}")
    df_display["holdings_value"] = df_display["holdings_value"].map(lambda x: f"${x:,.2f}")
    df_display["total_equity"]   = df_display["total_equity"].map(lambda x: f"${x:,.2f}")
    df_display.columns = ["DATE", "CASH", "HOLDINGS", "TOTAL EQUITY"]
    st.dataframe(df_display.iloc[::-1], use_container_width=True, hide_index=True)


# ─── TAB 4: MACRO DASHBOARD ───────────────────────────────────────────────────
def render_macro_dashboard():
    st.markdown(
        '<h3 style="color:#ffb000;letter-spacing:3px;">[ MACRO DASHBOARD ]</h3>',
        unsafe_allow_html=True
    )

    result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")

    if not result:
        terminal_text(
            "NO MACRO DATA LOADED\n\nClick [ INIT PORTFOLIO ] in the sidebar to fetch FRED indicators.",
            color="#555"
        )
        return

    # ── Macro Summary Table ──
    st.markdown(
        '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
        '═══ FRED MACRO INDICATORS ═══</div>',
        unsafe_allow_html=True
    )
    summary_rows = result.get("summary_rows", [])
    if summary_rows:
        df_macro = pd.DataFrame(summary_rows)[["indicator", "value", "unit", "trend", "interpretation"]]
        df_macro.columns = ["INDICATOR", "VALUE", "UNIT", "TREND", "INTERPRETATION"]

        def color_trend(val):
            if val == "rising":  return "color: #00ff41"
            if val == "falling": return "color: #ff3333"
            return "color: #ffb000"

        styled = df_macro.style.applymap(color_trend, subset=["TREND"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── Regime narrative ──
    st.markdown("<br>", unsafe_allow_html=True)
    narrative = result.get("regime_narrative", "")
    if narrative:
        st.markdown(
            '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;">'
            '═══ MACRO REGIME NARRATIVE ═══</div>',
            unsafe_allow_html=True
        )
        terminal_text(narrative, color="#00d4ff")

    # ── Axis Scoring (Phase 2) ──
    axis_scores = result.get("axis_scores", {})
    if axis_scores:
        st.markdown(
            '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;margin-top:1rem;">'
            '═══ AXIS SCORING BREAKDOWN ═══</div>',
            unsafe_allow_html=True
        )
        axis_rows = []
        for axis, data in axis_scores.items():
            axis_rows.append({
                "AXIS":       axis.replace("_", " / ").upper(),
                "FAVORED":    data.get("favored", "?"),
                "CONFIDENCE": f"{data.get('confidence', 0):.0%}",
                "REASONING":  data.get("reasoning", ""),
            })
        st.dataframe(pd.DataFrame(axis_rows), use_container_width=True, hide_index=True)

    # ── Allocation table + charts ──
    allocation = result.get("allocation", [])
    if not allocation:
        allocation = db.get_target_allocation()

    if allocation:
        st.markdown(
            '<div style="color:#ffb000;font-size:0.78rem;letter-spacing:2px;margin-top:1rem;">'
            '═══ STRATEGIC ALLOCATION ═══</div>',
            unsafe_allow_html=True
        )
        df_alloc = pd.DataFrame(allocation)
        df_alloc = df_alloc.sort_values("weight_pct", ascending=False)
        df_alloc["weight_pct"] = df_alloc["weight_pct"].map(lambda x: f"{x:.2f}%")
        df_alloc.columns = [c.upper().replace("_", " ") for c in df_alloc.columns]
        st.dataframe(df_alloc, use_container_width=True, hide_index=True)

        # Pie chart of allocation
        alloc_data = db.get_target_allocation() or allocation
        labels  = [f"{r.get('strategy_bucket','?')} ({r.get('ticker','?')})" for r in alloc_data]
        values  = [r.get("weight_pct", 0) for r in alloc_data]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(
                colors=[
                    "#00ff41", "#00d4ff", "#ffb000", "#ff6600",
                    "#008f11", "#0077aa", "#cc8800", "#cc4400",
                    "#00ff41", "#00d4ff", "#ffb000", "#ff6600",
                    "#005500", "#003355", "#553300", "#551100",
                ],
                line=dict(color="#0a0a0a", width=1),
            ),
            textfont=dict(color="#00ff41", family="Courier New", size=10),
            textinfo="label+percent",
        )])
        fig.update_layout(
            title=dict(text="BUCKET ALLOCATION", font=dict(color="#ffb000", family="Courier New", size=14)),
            paper_bgcolor="#050505",
            plot_bgcolor="#050505",
            font=dict(color="#00ff41", family="Courier New"),
            legend=dict(bgcolor="#050505", font=dict(color="#00ff41", size=9), bordercolor="#333"),
            height=500,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Bar chart: sub-strategy totals
        sub_totals = {"D": 0, "C": 0, "G": 0, "V": 0, "H": 0, "L": 0, "U": 0, "E": 0}
        raw_alloc  = db.get_target_allocation() or allocation
        for row in raw_alloc:
            b = row.get("strategy_bucket", "")
            w = row.get("weight_pct", 0)
            axes_map = macro_agent.BUCKET_AXES.get(b, {})
            for key in ["dc", "gv", "hl", "ue"]:
                sub = axes_map.get(key, "")
                if sub in sub_totals:
                    sub_totals[sub] += w

        fig2 = go.Figure(data=[go.Bar(
            x=list(sub_totals.keys()),
            y=list(sub_totals.values()),
            marker_color=["#00ff41" if v <= 70 else "#ff3333" for v in sub_totals.values()],
            text=[f"{v:.1f}%" for v in sub_totals.values()],
            textposition="outside",
            textfont=dict(color="#00ff41"),
        )])
        fig2.add_hline(y=70, line_dash="dot", line_color="#ff6600",
                       annotation_text="70% CAP", annotation_font_color="#ff6600")
        fig2.update_layout(
            title=dict(text="SUB-STRATEGY TOTALS vs. 70% CAP",
                       font=dict(color="#ffb000", family="Courier New", size=14)),
            paper_bgcolor="#050505",
            plot_bgcolor="#050505",
            font=dict(color="#00ff41", family="Courier New"),
            xaxis=dict(gridcolor="#1a1a1a", color="#008f11"),
            yaxis=dict(gridcolor="#1a1a1a", color="#008f11", range=[0, 80]),
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig2, use_container_width=True)


# ─── MAIN APP LAYOUT ──────────────────────────────────────────────────────────
def main():
    # Main entry point: renders ticker tape, sidebar, and tabbed content
    render_ticker_tape()
    render_sidebar()

    tab1, tab2, tab3, tab4 = st.tabs([
        "[ TRADING FLOOR ]",
        "[ PORTFOLIO ]",
        "[ PERFORMANCE ]",
        "[ MACRO DASHBOARD ]",
    ])

    with tab1:
        render_trading_floor()

    with tab2:
        render_portfolio()

    with tab3:
        render_performance()

    with tab4:
        render_macro_dashboard()


if __name__ == "__main__":
    main()
