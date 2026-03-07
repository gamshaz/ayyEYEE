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
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&display=swap');

html, body, [class*="css"], .stApp, .block-container,
div, p, span, label, button, input, select, textarea, th, td, li {
    font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
}

/* ── Background ── */
.stApp { background-color: #131722 !important; }
.block-container { background-color: #131722 !important; padding-top: 1rem !important; }
section[data-testid="stSidebar"] { background-color: #0e1219 !important; border-right: 1px solid #2a3244; }

/* ── Text colors ── */
body, .stMarkdown, p, span, label, div { color: #d4d4d4 !important; }
h1, h2, h3, h4, h5, h6 { color: #ff9900 !important; text-transform: uppercase; letter-spacing: 2px; }
.stMetric label { color: #7a8ba5 !important; font-size: 0.75rem !important; text-transform: uppercase; }
.stMetric [data-testid="stMetricValue"] { color: #ffffff !important; }
.stMetric [data-testid="stMetricDelta"] { font-size: 0.8rem !important; }

/* ── Buttons ── */
.stButton > button {
    background-color: #1a2035 !important;
    color: #ff9900 !important;
    border: 1px solid #ff9900 !important;
    border-radius: 2px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 0.4rem 1.2rem !important;
    transition: all 0.1s ease !important;
}
.stButton > button:hover {
    background-color: #ff9900 !important;
    color: #0e1219 !important;
}
.stButton > button:active {
    background-color: #cc7700 !important;
    color: #0e1219 !important;
}

/* ── Tab styling ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #0e1219 !important;
    border-bottom: 1px solid #ff9900 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    color: #7a8ba5 !important;
    background-color: #0e1219 !important;
    border: 1px solid #1e2a3a !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 0.5rem 1.5rem !important;
}
.stTabs [aria-selected="true"] {
    color: #ff9900 !important;
    background-color: #131722 !important;
    border-bottom: 2px solid #ff9900 !important;
}

/* ── DataFrames / Tables ── */
.stDataFrame, .dataframe { background-color: #0e1219 !important; }
.stDataFrame thead th {
    background-color: #1a2035 !important;
    color: #ff9900 !important;
    font-size: 0.75rem !important;
    text-transform: uppercase !important;
    border: 1px solid #2a3244 !important;
}
.stDataFrame tbody td {
    background-color: #111827 !important;
    color: #d4d4d4 !important;
    border: 1px solid #1e2a3a !important;
    font-size: 0.78rem !important;
}

/* ── Input fields ── */
.stTextInput input, .stTextArea textarea, .stSelectbox select {
    background-color: #0e1219 !important;
    color: #d4d4d4 !important;
    border: 1px solid #2a3244 !important;
    border-radius: 2px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0e1219; }
::-webkit-scrollbar-thumb { background: #2a3244; border-radius: 2px; }

/* ── Success / warning / error overrides ── */
.stAlert { border-radius: 2px !important; border-left: 3px solid #ff9900 !important; }
div[data-testid="stNotification"] { background-color: #0e1219 !important; }

/* ── Sidebar text ── */
section[data-testid="stSidebar"] * { color: #d4d4d4 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #ff9900 !important; }

/* ── Plotly chart backgrounds ── */
.js-plotly-plot .plotly { background: #131722 !important; }
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
            f'<div style="color:#ff9900;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            f'font-size:0.78rem;margin:0.5rem 0;">'
            f'{"═"*4} {label.upper()} {"═"*(max(4, 60-len(label)-6))}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="color:#2a3244;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.78rem;margin:0.4rem 0;">'
            '{"─"*64}</div>',
            unsafe_allow_html=True
        )


def terminal_text(text: str, color: str = "#d4d4d4", size: str = "0.8rem"):
    # Renders monospace terminal-style text
    st.markdown(
        f'<pre style="color:{color};font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
        f'font-size:{size};background:#0e1219;padding:0.8rem;'
        f'border:1px solid #2a3244;overflow-x:auto;">{text}</pre>',
        unsafe_allow_html=True
    )


def render_terminal_table(df: pd.DataFrame, color_fns: dict = None):
    """Render a DataFrame as a Bloomberg-styled HTML table.

    color_fns: {col_name: callable(value) -> css color string}
    """
    if df.empty:
        terminal_text("NO DATA", color="#555")
        return

    headers = "".join(
        f'<th style="background:#1a2035;color:#ff9900;font-size:0.72rem;'
        f'text-transform:uppercase;border:1px solid #2a3244;padding:0.35rem 0.7rem;'
        f'letter-spacing:1px;white-space:nowrap;font-weight:500;">{col}</th>'
        for col in df.columns
    )

    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        row_bg = "#111827" if i % 2 == 0 else "#0e1219"
        cells = ""
        for col in df.columns:
            val = row[col]
            color = "#d4d4d4"
            if color_fns and col in color_fns:
                color = color_fns[col](val)
            cells += (
                f'<td style="background:{row_bg};color:{color};font-size:0.78rem;'
                f'border:1px solid #1e2a3a;padding:0.3rem 0.7rem;white-space:nowrap;">'
                f'{val}</td>'
            )
        rows_html += f"<tr>{cells}</tr>"

    html = (
        '<div style="overflow-x:auto;margin:0.4rem 0;">'
        '<table style="width:100%;border-collapse:collapse;'
        "font-family:'IBM Plex Mono','Courier New',monospace;\">"
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _pnl_color(val):
    try:
        num = float(str(val).replace("+", "").replace("%", "").replace("$", "").replace(",", ""))
        return "#4caf50" if num >= 0 else "#f44336"
    except Exception:
        return "#d4d4d4"


def _trend_color(val):
    v = str(val).lower()
    if v == "rising":  return "#4caf50"
    if v == "falling": return "#f44336"
    return "#ff9900"


def _action_color(val):
    v = str(val).upper()
    if v in ("BUY", "INIT_BUY"):  return "#4caf50"
    if v == "SELL":                return "#f44336"
    return "#ff9900"


# ─── TOP TICKER TAPE ──────────────────────────────────────────────────────────
def render_ticker_tape():
    # Renders the top-of-page Bloomberg-style portfolio metrics bar
    pf = load_portfolio_state()
    tv = pf["total_value"]
    cash = pf["cash"]
    dpnl = pf["daily_pnl"]
    dpct = pf["daily_pnl_pct"]
    tret = pf["total_return_pct"]

    dpnl_color = "#4caf50" if dpnl >= 0 else "#f44336"
    tret_color = "#4caf50" if tret >= 0 else "#f44336"
    dpnl_sign  = "+" if dpnl >= 0 else ""
    tret_sign  = "+" if tret >= 0 else ""

    tape_html = f"""
    <div style="
        background:#0e1219;
        border:1px solid #2a3244;
        border-left:3px solid #ff9900;
        border-radius:2px;
        padding:0.6rem 1.5rem;
        margin-bottom:1rem;
        font-family:'IBM Plex Mono','Courier New',monospace;
        font-size:0.82rem;
        display:flex;
        flex-wrap:wrap;
        gap:2rem;
        align-items:center;
    ">
        <span style="color:#ff9900;font-weight:500;letter-spacing:2px;font-size:0.85rem;">
            PAPER TRADING TERMINAL
        </span>
        <span style="color:#2a3244;">|</span>
        <span>
            <span style="color:#7a8ba5;">PORTFOLIO</span>
            <span style="color:#ffffff;"> ${tv:,.2f}</span>
        </span>
        <span>
            <span style="color:#7a8ba5;">CASH</span>
            <span style="color:#d4d4d4;"> ${cash:,.2f}</span>
        </span>
        <span>
            <span style="color:#7a8ba5;">DAILY P&L</span>
            <span style="color:{dpnl_color};"> {dpnl_sign}${dpnl:,.2f} ({dpnl_sign}{dpct:.2f}%)</span>
        </span>
        <span>
            <span style="color:#7a8ba5;">TOTAL RETURN</span>
            <span style="color:{tret_color};"> {tret_sign}{tret:.2f}%</span>
        </span>
        <span>
            <span style="color:#7a8ba5;">SIM DATE</span>
            <span style="color:#ff9900;"> {st.session_state.current_date}</span>
        </span>
    </div>
    """
    st.markdown(tape_html, unsafe_allow_html=True)


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
def render_sidebar():
    # Renders the command panel sidebar with controls and status indicators
    with st.sidebar:
        # ── LOGO — drop logo.png into the project folder to display it ──
        import os
        _logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(_logo_path):
            st.image(_logo_path, use_container_width=True)
            st.markdown("<br>", unsafe_allow_html=True)

        st.markdown(
            '<div style="color:#ff9900;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.85rem;font-weight:500;letter-spacing:2px;border-bottom:'
            '1px solid #2a3244;padding-bottom:0.5rem;margin-bottom:1rem;text-transform:uppercase;">'
            'Command Panel</div>',
            unsafe_allow_html=True
        )

        # Simulation date display
        st.markdown(
            f'<div style="color:#7a8ba5;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            f'font-size:0.8rem;margin-bottom:0.8rem;">'
            f'SIM DATE <span style="color:#ff9900;">{st.session_state.current_date}</span></div>',
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ── INIT PORTFOLIO ──
        if st.button("[ INIT PORTFOLIO ]", key="btn_init", use_container_width=True):
            _handle_init_portfolio()

        # ── CONFIRM MACRO ── (shown only after phase 1 complete, before phase 2)
        if st.session_state.macro_phase1_done and not st.session_state.macro_confirmed:
            st.markdown(
                '<div style="color:#ff9900;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
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
                f'<div style="color:#ff9900;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
                f'font-size:0.75rem;">{n} APPROVED TRADE(S) PENDING</div>',
                unsafe_allow_html=True
            )
            if st.button("[ EXECUTE TRADES ]", key="btn_execute", use_container_width=True):
                _handle_execute_trades()

        # ── RUN N DAYS ──
        st.markdown(
            '<div style="color:#7a8ba5;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;margin:0.5rem 0 0.3rem;">AUTO-RUN N DAYS</div>',
            unsafe_allow_html=True
        )
        n_days = st.number_input(
            "Days", min_value=1, max_value=60, value=5, step=1,
            key="n_days_input", label_visibility="collapsed"
        )
        if st.button("[ RUN N DAYS ]", key="btn_run_n", use_container_width=True):
            _handle_run_n_days(n_days)

        st.markdown("---")

        # ── STATUS ──
        status_color = "#4caf50" if st.session_state.sim_started else "#ff9900"
        status_label = "LIVE" if st.session_state.sim_started else "OFFLINE"
        last_run = st.session_state.last_run_time or "—"
        st.markdown(
            f'<div style="font-family:\'IBM Plex Mono\',\'Courier New\',monospace;font-size:0.75rem;color:#7a8ba5;">'
            f'STATUS <span style="color:{status_color};">● {status_label}</span><br>'
            f'LAST RUN <span style="color:#d4d4d4;">{last_run}</span>'
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


def _handle_run_n_days(n: int):
    # Runs the full Advance Day → Run Agents → Execute Trades loop N times
    if not st.session_state.sim_started:
        st.warning("INITIALIZE PORTFOLIO FIRST")
        return

    progress_bar      = st.progress(0)
    status_placeholder = st.empty()

    for i in range(n):
        # ── Step 1: Advance day ──
        current  = datetime.strptime(st.session_state.current_date, "%Y-%m-%d")
        next_day = current + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        st.session_state.current_date = next_day.strftime("%Y-%m-%d")

        status_placeholder.info(f"DAY {i+1}/{n} — {st.session_state.current_date}  (fetching prices...)")
        try:
            prices = data_utils.get_all_current_prices(st.session_state.current_date)
            st.session_state.prices = prices
            if prices:
                execution_agent.refresh_position_prices(prices)
        except Exception as e:
            st.error(f"PRICE FETCH ERROR on {st.session_state.current_date}: {e}")
            break

        # ── Step 2: Run agents ──
        status_placeholder.info(f"DAY {i+1}/{n} — {st.session_state.current_date}  (running agents...)")
        try:
            positions = db.get_positions()
            state     = db.get_simulation_state()
            cash      = state["cash_balance"]          if state else db.INITIAL_CASH
            pf_value  = state["total_portfolio_value"] if state else db.INITIAL_CASH

            proposed          = tactical_agent.propose_trades(
                st.session_state.current_date, positions, prices, pf_value
            )
            approved, rejected = risk_agent.validate_trades(proposed, positions, cash, pf_value, prices)
            st.session_state.proposed_trades = proposed
            st.session_state.approved_trades = approved
            st.session_state.rejected_trades = rejected
        except Exception as e:
            st.error(f"AGENT ERROR on {st.session_state.current_date}: {e}")
            break

        # ── Step 3: Execute trades ──
        status_placeholder.info(f"DAY {i+1}/{n} — {st.session_state.current_date}  (executing trades...)")
        try:
            positions = db.get_positions()
            state     = db.get_simulation_state()
            cash      = state["cash_balance"] if state else db.INITIAL_CASH

            result = execution_agent.execute_trades(
                approved,
                st.session_state.current_date,
                prices,
                cash,
                positions,
            )
            updated_positions = db.get_positions()
            execution_agent.save_daily_snapshot(
                st.session_state.current_date, result["new_cash"], updated_positions, prices
            )
            st.session_state.agent_log       = result["execution_log"]
            st.session_state.approved_trades = []
            st.session_state.proposed_trades = []
        except Exception as e:
            st.error(f"EXECUTION ERROR on {st.session_state.current_date}: {e}")
            break

        progress_bar.progress((i + 1) / n)

    st.session_state.last_run_time = datetime.now().strftime("%H:%M:%S")
    status_placeholder.success(f"COMPLETED {n} DAY(S) — NOW AT {st.session_state.current_date}")
    st.rerun()


# ─── TAB 1: TRADING FLOOR ─────────────────────────────────────────────────────
def render_trading_floor():
    st.markdown(
        '<h3 style="color:#ff9900;letter-spacing:2px;font-weight:500;">[ TRADING FLOOR ]</h3>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
            '═══ MACRO REGIME ═══</div>',
            unsafe_allow_html=True
        )
        result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")
        if result:
            narrative = result.get("regime_narrative", "—")
            terminal_text(narrative, color="#d4d4d4")
        else:
            terminal_text("NO MACRO DATA — RUN [ INIT PORTFOLIO ]", color="#555")

    with col2:
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
            '═══ PROPOSED TRADES ═══</div>',
            unsafe_allow_html=True
        )
        if st.session_state.proposed_trades:
            df_trades = pd.DataFrame(st.session_state.proposed_trades)
            render_terminal_table(df_trades)
        else:
            terminal_text("NO TRADES PROPOSED — RUN [ RUN AGENTS ]", color="#555")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ AGENT REASONING LOG ═══</div>',
        unsafe_allow_html=True
    )

    # ── APPROVED TRADES ──
    if st.session_state.approved_trades:
        st.markdown(
            '<div style="color:#4caf50;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin-bottom:0.3rem;">'
            '▶ APPROVED TRADES</div>',
            unsafe_allow_html=True,
        )
        approved_rows = [
            {
                "ACTION": t.get("action", "?").upper(),
                "TICKER": t.get("symbol", "?"),
                "SHARES": f"{t.get('shares', 0):,.2f}",
                "REASON": t.get("reason", ""),
            }
            for t in st.session_state.approved_trades
        ]
        render_terminal_table(pd.DataFrame(approved_rows), color_fns={"ACTION": _action_color})

    # ── REJECTED TRADES ──
    if st.session_state.rejected_trades:
        st.markdown(
            '<div style="color:#f44336;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin:0.6rem 0 0.3rem;">'
            '✕ REJECTED TRADES</div>',
            unsafe_allow_html=True,
        )
        rejected_rows = [
            {
                "ACTION": t.get("action", "?").upper(),
                "TICKER": t.get("symbol", "?"),
                "REASON": t.get("rejection_reason", ""),
            }
            for t in st.session_state.rejected_trades
        ]
        render_terminal_table(
            pd.DataFrame(rejected_rows),
            color_fns={"ACTION": lambda _: "#f44336"},
        )

    # ── EXECUTION LOG ──
    if st.session_state.agent_log:
        st.markdown(
            '<div style="color:#7a8ba5;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin:0.6rem 0 0.3rem;">'
            '■ EXECUTION LOG</div>',
            unsafe_allow_html=True,
        )
        terminal_text(st.session_state.agent_log)

    # ── Fallback when nothing to show ──
    if (not st.session_state.approved_trades
            and not st.session_state.rejected_trades
            and not st.session_state.agent_log):
        terminal_text("NO LOG ENTRIES — RUN [ ADVANCE DAY ] → [ RUN AGENTS ] → [ EXECUTE TRADES ]", color="#555")


# ─── TAB 2: PORTFOLIO ─────────────────────────────────────────────────────────
def render_portfolio():
    st.markdown(
        '<h3 style="color:#ff9900;letter-spacing:2px;font-weight:500;">[ PORTFOLIO HOLDINGS ]</h3>',
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

    render_terminal_table(df, color_fns={"P&L": _pnl_color, "P&L%": _pnl_color})

    # Portfolio totals
    total_pnl = total_mv - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    pnl_color = "#4caf50" if total_pnl >= 0 else "#f44336"

    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',\'Courier New\',monospace;font-size:0.8rem;'
        f'border-top:1px solid #2a3244;padding-top:0.5rem;margin-top:0.5rem;color:#7a8ba5;">'
        f'<span style="color:#ff9900;">TOTAL HOLDINGS</span> '
        f'<span style="color:#ffffff;">${total_mv:,.2f}</span>'
        f' &nbsp;|&nbsp; '
        f'<span style="color:#ff9900;">TOTAL P&L</span> '
        f'<span style="color:{pnl_color};">'
        f'{"+" if total_pnl>=0 else ""}${total_pnl:,.2f} '
        f'({"+" if total_pnl_pct>=0 else ""}{total_pnl_pct:.2f}%)'
        f'</span></div>',
        unsafe_allow_html=True
    )

    # ── Portfolio Treemap Heatmap ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ POSITION HEATMAP ═══</div>',
        unsafe_allow_html=True
    )
    tree_labels = []
    tree_parents = []
    tree_values = []
    tree_colors = []
    tree_text = []
    for r in rows:
        ticker = r["TICKER"]
        mv = float(r["MKT VALUE"].replace("$", "").replace(",", ""))
        pnl_pct = float(r["P&L%"].replace("+", "").replace("%", ""))
        tree_labels.append(f"{ticker}<br>{r['P&L%']}")
        tree_parents.append("")
        tree_values.append(mv)
        tree_colors.append(pnl_pct)
        tree_text.append(f"{ticker} | {r['MKT VALUE']} | P&L: {r['P&L%']}")

    if tree_values:
        fig_tree = go.Figure(go.Treemap(
            labels=tree_labels,
            parents=tree_parents,
            values=tree_values,
            marker=dict(
                colors=tree_colors,
                colorscale=[
                    [0.0, "#b71c1c"], [0.25, "#f44336"], [0.45, "#424242"],
                    [0.55, "#424242"], [0.75, "#4caf50"], [1.0, "#1b5e20"],
                ],
                cmid=0,
                colorbar=dict(
                    title=dict(text="P&L %", font=dict(color="#d4d4d4")),
                    tickfont=dict(color="#d4d4d4"),
                    ticksuffix="%",
                    bgcolor="#131722",
                    bordercolor="#2a3244",
                ),
                line=dict(color="#131722", width=2),
            ),
            text=tree_text,
            textfont=dict(family="IBM Plex Mono", size=12),
            textinfo="label",
            hovertemplate="%{text}<extra></extra>",
        ))
        fig_tree.update_layout(
            title=dict(text="HOLDINGS HEATMAP — SIZE = WEIGHT, COLOR = P&L",
                       font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#131722",
            font=dict(color="#ffffff", family="IBM Plex Mono"),
            height=420,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    # Recent transactions
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ RECENT TRANSACTIONS ═══</div>',
        unsafe_allow_html=True
    )
    txns = db.get_transactions()[:20]
    if txns:
        df_txns = pd.DataFrame(txns)[["date", "action", "symbol", "shares", "price", "reason"]]
        df_txns["shares"] = df_txns["shares"].map(lambda x: f"{x:,.4f}")
        df_txns["price"]  = df_txns["price"].map(lambda x: f"${x:,.4f}")
        df_txns.columns   = ["DATE", "ACTION", "TICKER", "SHARES", "PRICE", "REASON"]
        render_terminal_table(df_txns, color_fns={"ACTION": _action_color})
    else:
        terminal_text("NO TRANSACTIONS YET", color="#555")


# ─── TAB 3: PERFORMANCE ───────────────────────────────────────────────────────
def render_performance():
    st.markdown(
        '<h3 style="color:#ff9900;letter-spacing:2px;font-weight:500;">[ PERFORMANCE ANALYTICS ]</h3>',
        unsafe_allow_html=True
    )
    snapshots = db.get_daily_snapshots()

    if len(snapshots) < 2:
        terminal_text("INSUFFICIENT DATA — RUN SIMULATION FOR AT LEAST 2 DAYS", color="#555")
        return

    df_snap = pd.DataFrame(snapshots)
    df_snap["date"] = pd.to_datetime(df_snap["date"])
    initial_equity  = df_snap["total_equity"].iloc[0]

    # Warn when all snapshots are identical (happens when running future-date
    # simulation before real market data exists for those dates)
    if df_snap["total_equity"].std() < 1.0:
        st.markdown(
            '<div style="background:#1a1a00;border:1px solid #ff9900;border-left:3px solid #ff9900;'
            'border-radius:2px;padding:0.6rem 1rem;margin-bottom:0.8rem;font-family:\'IBM Plex Mono\','
            '\'Courier New\',monospace;font-size:0.75rem;color:#ff9900;">'
            'NOTE: Portfolio equity is flat. This is expected when simulation dates have advanced '
            'beyond the last available market close — yfinance returns the most recent known price '
            'for all future dates. P&amp;L will populate once real trading days with new closes are reached.'
            '</div>',
            unsafe_allow_html=True,
        )

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
        ret_color = "#4caf50" if total_return >= 0 else "#f44336"
        st.markdown(
            f'<div style="background:#0e1219;border:1px solid #2a3244;border-top:2px solid #ff9900;padding:1rem;text-align:center;border-radius:2px;">'
            f'<div style="color:#7a8ba5;font-size:0.7rem;letter-spacing:1px;margin-bottom:0.4rem;">TOTAL RETURN</div>'
            f'<div style="color:{ret_color};font-size:1.3rem;font-weight:500;">'
            f'{"+"if total_return>=0 else ""}{total_return:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c2:
        dd_color = "#f44336" if max_drawdown < -5 else "#ff9900"
        st.markdown(
            f'<div style="background:#0e1219;border:1px solid #2a3244;border-top:2px solid #ff9900;padding:1rem;text-align:center;border-radius:2px;">'
            f'<div style="color:#7a8ba5;font-size:0.7rem;letter-spacing:1px;margin-bottom:0.4rem;">MAX DRAWDOWN</div>'
            f'<div style="color:{dd_color};font-size:1.3rem;font-weight:500;">'
            f'{max_drawdown:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c3:
        sh_color = "#4caf50" if sharpe > 1 else ("#ff9900" if sharpe > 0 else "#f44336")
        st.markdown(
            f'<div style="background:#0e1219;border:1px solid #2a3244;border-top:2px solid #ff9900;padding:1rem;text-align:center;border-radius:2px;">'
            f'<div style="color:#7a8ba5;font-size:0.7rem;letter-spacing:1px;margin-bottom:0.4rem;">SHARPE RATIO</div>'
            f'<div style="color:{sh_color};font-size:1.3rem;font-weight:500;">'
            f'{sharpe:.2f}</div></div>',
            unsafe_allow_html=True
        )
    with c4:
        wr_color = "#4caf50" if win_rate > 50 else "#f44336"
        st.markdown(
            f'<div style="background:#0e1219;border:1px solid #2a3244;border-top:2px solid #ff9900;padding:1rem;text-align:center;border-radius:2px;">'
            f'<div style="color:#7a8ba5;font-size:0.7rem;letter-spacing:1px;margin-bottom:0.4rem;">WIN RATE</div>'
            f'<div style="color:{wr_color};font-size:1.3rem;font-weight:500;">'
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
        line=dict(color="#4caf50", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df_snap["date"],
        y=[initial_equity] * len(df_snap),
        mode="lines",
        name="Initial Capital",
        line=dict(color="#ff9900", width=1, dash="dot"),
    ))
    fig.update_layout(
        title=dict(text="EQUITY CURVE", font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
        paper_bgcolor="#131722",
        plot_bgcolor="#0e1219",
        font=dict(color="#d4d4d4", family="IBM Plex Mono"),
        xaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5", showgrid=True),
        yaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5", showgrid=True,
                   tickformat="$,.0f", autorange=True, rangemode="normal"),
        legend=dict(bgcolor="#0e1219", bordercolor="#2a3244", font=dict(color="#d4d4d4")),
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
        title=dict(text="DRAWDOWN (%)", font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
        paper_bgcolor="#131722",
        plot_bgcolor="#0e1219",
        font=dict(color="#d4d4d4", family="IBM Plex Mono"),
        xaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5"),
        yaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5", tickformat=".2f"),
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── ETF Correlation Matrix (FX-matrix style) ──
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ ETF CORRELATION MATRIX ═══</div>',
        unsafe_allow_html=True
    )
    try:
        sim_date = st.session_state.current_date
        price_hist = data_utils.get_price_history_with_warmup(sim_date)
        if not price_hist.empty and len(price_hist) >= 5:
            returns = price_hist.pct_change().dropna()
            # Only keep tickers we hold
            held_tickers = [p["symbol"] for p in db.get_positions()]
            avail = [t for t in held_tickers if t in returns.columns]
            if len(avail) >= 2:
                corr = returns[avail].corr()
                fig_corr = go.Figure(data=go.Heatmap(
                    z=corr.values,
                    x=corr.columns.tolist(),
                    y=corr.index.tolist(),
                    colorscale=[
                        [0.0, "#b71c1c"], [0.25, "#f44336"],
                        [0.5, "#1a1a2e"],
                        [0.75, "#4caf50"], [1.0, "#1b5e20"],
                    ],
                    zmin=-1, zmax=1,
                    text=corr.values.round(2),
                    texttemplate="%{text}",
                    textfont=dict(size=10, color="#ffffff", family="IBM Plex Mono"),
                    colorbar=dict(
                        title=dict(text="Corr", font=dict(color="#d4d4d4")),
                        tickfont=dict(color="#d4d4d4"),
                        bgcolor="#131722", bordercolor="#2a3244",
                    ),
                    hovertemplate="%{x} vs %{y}: %{z:.3f}<extra></extra>",
                ))
                fig_corr.update_layout(
                    title=dict(text="RETURN CORRELATION MATRIX",
                               font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
                    paper_bgcolor="#131722",
                    plot_bgcolor="#0e1219",
                    font=dict(color="#d4d4d4", family="IBM Plex Mono"),
                    xaxis=dict(color="#7a8ba5", tickangle=-45),
                    yaxis=dict(color="#7a8ba5", autorange="reversed"),
                    height=500,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                terminal_text("INSUFFICIENT HELD TICKERS FOR CORRELATION MATRIX", color="#555")
        else:
            terminal_text("INSUFFICIENT PRICE HISTORY FOR CORRELATION MATRIX", color="#555")
    except Exception as e:
        terminal_text(f"CORRELATION MATRIX ERROR: {e}", color="#f44336")

    # ── Daily snapshots table ──
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ DAILY SNAPSHOTS ═══</div>',
        unsafe_allow_html=True
    )
    df_display = df_snap[["date", "cash", "holdings_value", "total_equity"]].copy()
    df_display["date"]           = df_display["date"].dt.strftime("%Y-%m-%d")
    df_display["cash"]           = df_display["cash"].map(lambda x: f"${x:,.2f}")
    df_display["holdings_value"] = df_display["holdings_value"].map(lambda x: f"${x:,.2f}")
    df_display["total_equity"]   = df_display["total_equity"].map(lambda x: f"${x:,.2f}")
    df_display.columns = ["DATE", "CASH", "HOLDINGS", "TOTAL EQUITY"]
    render_terminal_table(df_display.iloc[::-1].reset_index(drop=True))


# ─── TAB 4: MACRO DASHBOARD ───────────────────────────────────────────────────
def render_macro_dashboard():
    st.markdown(
        '<h3 style="color:#ff9900;letter-spacing:2px;font-weight:500;">[ MACRO DASHBOARD ]</h3>',
        unsafe_allow_html=True
    )

    # ── Factor Drift: Target vs Actual ──
    positions = db.get_positions()
    target_alloc = db.get_target_allocation()
    if positions and target_alloc:
        prices = st.session_state.prices or {}
        total_mv = sum(p["shares"] * prices.get(p["symbol"], p.get("current_price", 0)) for p in positions) or 1

        # Compute actual sub-strategy weights from positions
        actual_sub = {"D": 0, "C": 0, "G": 0, "V": 0, "H": 0, "L": 0, "U": 0, "E": 0}
        for pos in positions:
            mv = pos["shares"] * prices.get(pos["symbol"], pos.get("current_price", 0))
            axes = macro_agent.BUCKET_AXES.get(pos["strategy_bucket"], {})
            w = mv / total_mv * 100
            for axis_key in ["dc", "gv", "hl", "ue"]:
                sub = axes.get(axis_key, "")
                if sub in actual_sub:
                    actual_sub[sub] += w

        # Compute target sub-strategy weights
        target_sub = {"D": 0, "C": 0, "G": 0, "V": 0, "H": 0, "L": 0, "U": 0, "E": 0}
        for row in target_alloc:
            axes = macro_agent.BUCKET_AXES.get(row["strategy_bucket"], {})
            w = row["weight_pct"]
            for axis_key in ["dc", "gv", "hl", "ue"]:
                sub = axes.get(axis_key, "")
                if sub in target_sub:
                    target_sub[sub] += w

        factor_names = {
            "D": "Defensive", "C": "Cyclical", "G": "Growth", "V": "Value",
            "H": "Hi-Beta", "L": "Lo-Beta", "U": "US", "E": "EM"
        }
        factors = list(factor_names.keys())
        target_vals = [target_sub[f] for f in factors]
        actual_vals = [actual_sub[f] for f in factors]
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
            '═══ FACTOR DRIFT: TARGET vs ACTUAL ═══</div>',
            unsafe_allow_html=True
        )

        # Grouped bar chart: target vs actual
        fig_drift = go.Figure()
        fig_drift.add_trace(go.Bar(
            name="Target",
            x=[factor_names[f] for f in factors],
            y=target_vals,
            marker_color="#2a3244",
            marker_line=dict(color="#ff9900", width=1),
            text=[f"{v:.1f}%" for v in target_vals],
            textposition="outside",
            textfont=dict(color="#ff9900", size=10, family="IBM Plex Mono"),
        ))
        fig_drift.add_trace(go.Bar(
            name="Actual",
            x=[factor_names[f] for f in factors],
            y=actual_vals,
            marker_color=["#4caf50" if a >= t else "#f44336" for a, t in zip(actual_vals, target_vals)],
            text=[f"{v:.1f}%" for v in actual_vals],
            textposition="outside",
            textfont=dict(color="#ffffff", size=10, family="IBM Plex Mono"),
        ))
        fig_drift.add_hline(y=70, line_dash="dot", line_color="#ffffff",
                            annotation_text="70% CAP", annotation_font_color="#ffffff",
                            annotation_font_size=10)
        fig_drift.update_layout(
            barmode="group",
            title=dict(text="FACTOR ALLOCATION: TARGET vs ACTUAL",
                       font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#131722",
            plot_bgcolor="#0e1219",
            font=dict(color="#d4d4d4", family="IBM Plex Mono"),
            xaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5"),
            yaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5", ticksuffix="%", range=[0, 100]),
            legend=dict(bgcolor="#0e1219", bordercolor="#2a3244", font=dict(color="#d4d4d4", size=9)),
            height=380,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_drift, use_container_width=True)

        # Delta summary cards
        delta_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:1rem;">'
        for f in factors:
            d = actual_sub[f] - target_sub[f]
            arrow = "+" if d >= 0 else ""
            color = "#4caf50" if abs(d) < 3 else ("#ffa726" if abs(d) < 7 else "#f44336")
            delta_html += (
                f'<div style="background:#0e1219;border:1px solid {color};border-radius:3px;'
                f'padding:6px 12px;text-align:center;min-width:80px;">'
                f'<div style="color:#7a8ba5;font-size:0.65rem;letter-spacing:1px;">{factor_names[f].upper()}</div>'
                f'<div style="color:{color};font-size:1rem;font-weight:500;">{arrow}{d:.1f}%</div>'
                f'</div>'
            )
        delta_html += '</div>'
        st.markdown(delta_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")

    if not result:
        terminal_text(
            "NO MACRO DATA LOADED\n\nClick [ INIT PORTFOLIO ] in the sidebar to fetch FRED indicators.",
            color="#555"
        )
        return

    # ── Macro Summary Table ──
    st.markdown(
        '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
        '═══ FRED MACRO INDICATORS ═══</div>',
        unsafe_allow_html=True
    )
    summary_rows = result.get("summary_rows", [])
    if summary_rows:
        df_macro = pd.DataFrame(summary_rows)[["indicator", "value", "unit", "trend", "interpretation"]]
        df_macro.columns = ["INDICATOR", "VALUE", "UNIT", "TREND", "INTERPRETATION"]
        render_terminal_table(df_macro, color_fns={"TREND": _trend_color})

    # ── Regime narrative ──
    st.markdown("<br>", unsafe_allow_html=True)
    narrative = result.get("regime_narrative", "")
    if narrative:
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;">'
            '═══ MACRO REGIME NARRATIVE ═══</div>',
            unsafe_allow_html=True
        )
        terminal_text(narrative, color="#d4d4d4")

    # ── Axis Scoring (Phase 2) ──
    axis_scores = result.get("axis_scores", {})
    if axis_scores:
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;margin-top:1rem;">'
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
        render_terminal_table(pd.DataFrame(axis_rows))

    # ── Allocation table + charts ──
    allocation = result.get("allocation", [])
    if not allocation:
        allocation = db.get_target_allocation()

    if allocation:
        st.markdown(
            '<div style="color:#ff9900;font-size:0.72rem;letter-spacing:2px;font-weight:500;margin-top:1rem;">'
            '═══ STRATEGIC ALLOCATION ═══</div>',
            unsafe_allow_html=True
        )
        df_alloc = pd.DataFrame(allocation)
        df_alloc = df_alloc.sort_values("weight_pct", ascending=False)
        df_alloc["weight_pct"] = df_alloc["weight_pct"].map(lambda x: f"{x:.2f}%")
        df_alloc.columns = [c.upper().replace("_", " ") for c in df_alloc.columns]
        render_terminal_table(df_alloc.reset_index(drop=True))

        # Pie chart of ACTUAL allocation (from live positions)
        positions = db.get_positions()
        total_mv = sum(p["market_value"] for p in positions) or 1
        actual_alloc = [
            {"strategy_bucket": p["strategy_bucket"], "ticker": p["symbol"],
             "weight_pct": p["market_value"] / total_mv * 100}
            for p in positions if p["market_value"] > 0
        ]
        alloc_data = actual_alloc if actual_alloc else (db.get_target_allocation() or allocation)
        labels  = [f"{r.get('strategy_bucket','?')} ({r.get('ticker','?')})" for r in alloc_data]
        values  = [r.get("weight_pct", 0) for r in alloc_data]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            marker=dict(
                colors=[
                    "#4caf50", "#2196f3", "#ff9900", "#f44336",
                    "#26a69a", "#1565c0", "#e65100", "#b71c1c",
                    "#66bb6a", "#42a5f5", "#ffa726", "#ef5350",
                    "#1b5e20", "#0d47a1", "#bf360c", "#7f0000",
                ],
                line=dict(color="#131722", width=1),
            ),
            textfont=dict(color="#ffffff", family="IBM Plex Mono", size=10),
            textinfo="label+percent",
        )])
        fig.update_layout(
            title=dict(text="BUCKET ALLOCATION", font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#131722",
            plot_bgcolor="#131722",
            font=dict(color="#d4d4d4", family="IBM Plex Mono"),
            legend=dict(bgcolor="#0e1219", font=dict(color="#d4d4d4", size=9), bordercolor="#2a3244"),
            height=500,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Bar chart: sub-strategy totals (from live positions)
        sub_totals = {"D": 0, "C": 0, "G": 0, "V": 0, "H": 0, "L": 0, "U": 0, "E": 0}
        raw_alloc  = actual_alloc if actual_alloc else (db.get_target_allocation() or allocation)
        for row in raw_alloc:
            b = row.get("strategy_bucket", "")
            w = row.get("weight_pct", 0)
            axes_map = macro_agent.BUCKET_AXES.get(b, {})
            for key in ["dc", "gv", "hl", "ue"]:
                sub = axes_map.get(key, "")
                if sub in sub_totals:
                    sub_totals[sub] += w

        # Stacked bar chart: opposing factor pairs side by side
        # Each bar = one axis; two stacked segments = the two opposing sub-strategies
        pair_labels = ["Defensive / Cyclical", "Growth / Value", "High Beta / Low Beta", "US / EM"]
        first_subs  = ["D",  "G",  "H",  "U"]   # upper segment colors
        second_subs = ["C",  "V",  "L",  "E"]   # lower segment colors
        # Contrasting colors per pair:  Defensive=green, Cyclical=amber
        #                               Growth=cyan,     Value=orange
        #                               High Beta=red,   Low Beta=blue
        #                               US=bright-green, EM=yellow
        first_colors  = ["#4caf50", "#00d4ff", "#f44336", "#66bb6a"]
        second_colors = ["#ff9900", "#ff6600", "#2196f3", "#ffd600"]

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Defensive / Growth / Hi-β / US",
            x=pair_labels,
            y=[sub_totals[s] for s in first_subs],
            marker_color=first_colors,
            text=[f"{sub}: {sub_totals[sub]:.1f}%" for sub in first_subs],
            textposition="inside",
            textfont=dict(color="#ffffff", size=10, family="IBM Plex Mono"),
        ))
        fig2.add_trace(go.Bar(
            name="Cyclical / Value / Lo-β / EM",
            x=pair_labels,
            y=[sub_totals[s] for s in second_subs],
            marker_color=second_colors,
            text=[f"{sub}: {sub_totals[sub]:.1f}%" for sub in second_subs],
            textposition="inside",
            textfont=dict(color="#0e1219", size=10, family="IBM Plex Mono"),
        ))
        fig2.add_hline(y=70, line_dash="dot", line_color="#ffffff",
                       annotation_text="70% CAP", annotation_font_color="#ffffff")
        fig2.update_layout(
            barmode="stack",
            title=dict(text="FACTOR EXPOSURE vs. 70% SUB-STRATEGY CAP",
                       font=dict(color="#ff9900", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#131722",
            plot_bgcolor="#0e1219",
            font=dict(color="#d4d4d4", family="IBM Plex Mono"),
            xaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5"),
            yaxis=dict(gridcolor="#1e2a3a", color="#7a8ba5", range=[0, 110], ticksuffix="%"),
            legend=dict(bgcolor="#0e1219", bordercolor="#2a3244", font=dict(color="#d4d4d4", size=9)),
            height=380,
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
