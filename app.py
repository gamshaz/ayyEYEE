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

# ─── Modern Terminal CSS ───────────────────────────────────────────────────────
BLOOMBERG_CSS = """
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@300;400;500&display=swap');

/* ── Global reset & font ── */
html, body, [class*="css"], .stApp, .block-container,
div, p, span, label, button, input, select, textarea, th, td, li {
    font-family: 'IBM Plex Mono', 'Courier New', monospace !important;
}

/* ── Backgrounds ── */
.stApp { background-color: #080d1a !important; }
.block-container { background-color: #080d1a !important; padding-top: 1rem !important; }
section[data-testid="stSidebar"] {
    background-color: #060b18 !important;
    border-right: 1px solid #1a2540 !important;
}

/* ── Text ── */
body, .stMarkdown, p, span, label, div { color: #e2e8f0 !important; }
h1, h2, h3, h4, h5, h6 {
    color: #f59e0b !important;
    text-transform: uppercase;
    letter-spacing: 2px;
}
.stMetric label {
    color: #4a5878 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stMetric [data-testid="stMetricValue"] { color: #e2e8f0 !important; }
.stMetric [data-testid="stMetricDelta"] { font-size: 0.78rem !important; }

/* ── Buttons ── */
.stButton > button {
    background-color: #0d1526 !important;
    color: #f59e0b !important;
    border: 1px solid #f59e0b !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.76rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 0.4rem 1.2rem !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
.stButton > button:hover {
    background-color: #f59e0b !important;
    color: #080d1a !important;
}
.stButton > button:active {
    background-color: #d97706 !important;
    color: #080d1a !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background-color: #060b18 !important;
    border-bottom: 1px solid #1a2540 !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    color: #4a5878 !important;
    background-color: #060b18 !important;
    border: 1px solid #1a2540 !important;
    border-bottom: none !important;
    border-radius: 0 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.76rem !important;
    text-transform: uppercase !important;
    letter-spacing: 1.5px !important;
    padding: 0.55rem 1.6rem !important;
    transition: color 0.15s ease !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #e2e8f0 !important;
}
.stTabs [aria-selected="true"] {
    color: #f59e0b !important;
    background: linear-gradient(180deg, #0d1526 0%, #080d1a 100%) !important;
    border-bottom: 2px solid #f59e0b !important;
}

/* ── DataFrames ── */
.stDataFrame, .dataframe { background-color: #0d1526 !important; }
.stDataFrame thead th {
    background-color: #0a1020 !important;
    color: #f59e0b !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    border: 1px solid #1a2540 !important;
    letter-spacing: 1px;
}
.stDataFrame tbody td {
    background-color: #0d1526 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1a2540 !important;
    font-size: 0.76rem !important;
}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea {
    background-color: #0d1526 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.8rem !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 1px #3b82f6 !important;
}
.stSelectbox > div > div {
    background-color: #0d1526 !important;
    border: 1px solid #1a2540 !important;
    color: #e2e8f0 !important;
}
.stNumberInput input {
    background-color: #0d1526 !important;
    color: #e2e8f0 !important;
    border: 1px solid #1a2540 !important;
    border-radius: 3px !important;
    font-family: 'IBM Plex Mono', monospace !important;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #080d1a; }
::-webkit-scrollbar-thumb { background: #1a2540; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #3b82f6; }

/* ── Alerts ── */
.stAlert {
    border-radius: 3px !important;
    border-left: 3px solid #f59e0b !important;
    background-color: #0d1526 !important;
}
div[data-testid="stNotification"] { background-color: #0d1526 !important; }

/* ── Sidebar text ── */
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 { color: #f59e0b !important; }
section[data-testid="stSidebar"] hr {
    border-color: #1a2540 !important;
    margin: 0.6rem 0 !important;
}

/* ── Plotly chart backgrounds ── */
.js-plotly-plot .plotly { background: #080d1a !important; }

/* ── Section header tag ── */
.section-header {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin: 0.75rem 0 0.4rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: #f59e0b;
    font-variant: small-caps;
    font-weight: 500;
}
.section-header::after {
    content: '';
    flex: 1;
    height: 1px;
    background: #1a2540;
}
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


# ─── Helper: Modern section separator ─────────────────────────────────────────
def bsep(label: str = ""):
    # Renders a modern section header with label and extending line
    if label:
        st.markdown(
            f'<div class="section-header">{label.upper()}</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="height:1px;background:#1a2540;margin:0.6rem 0;"></div>',
            unsafe_allow_html=True
        )


def terminal_text(text: str, color: str = "#e2e8f0", size: str = "0.8rem"):
    # Renders monospace terminal-style text
    st.markdown(
        f'<pre style="color:{color};font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
        f'font-size:{size};background:#0d1526;padding:0.9rem 1rem;'
        f'border-left:3px solid #1a2540;border-radius:4px;'
        f'overflow-x:auto;margin:0.3rem 0;">{text}</pre>',
        unsafe_allow_html=True
    )


def render_terminal_table(df: pd.DataFrame, color_fns: dict = None):
    """Render a DataFrame as a modernized dark HTML table.

    color_fns: {col_name: callable(value) -> css color string}
    """
    if df.empty:
        terminal_text("NO DATA", color="#4a5878")
        return

    headers = "".join(
        f'<th style="background:#0a1020;color:#f59e0b;font-size:0.72rem;'
        f'text-transform:uppercase;border:1px solid #1a2540;padding:0.38rem 0.75rem;'
        f'letter-spacing:1.2px;white-space:nowrap;font-weight:500;">{col}</th>'
        for col in df.columns
    )

    rows_html = ""
    for i, (_, row) in enumerate(df.iterrows()):
        row_bg = "#0d1526" if i % 2 == 0 else "#0a1020"
        cells = ""
        for col in df.columns:
            val = row[col]
            color = "#e2e8f0"
            if color_fns and col in color_fns:
                color = color_fns[col](val)
            cells += (
                f'<td style="background:{row_bg};color:{color};font-size:0.76rem;'
                f'border:1px solid #1a2540;padding:0.32rem 0.75rem;white-space:nowrap;'
                f'transition:background 0.1s;">'
                f'{val}</td>'
            )
        rows_html += f'<tr style="transition:background 0.1s;" onmouseover="this.style.background=\'#111d35\'" onmouseout="this.style.background=\'\';">{cells}</tr>'

    html = (
        '<div style="overflow-x:auto;margin:0.35rem 0;border-radius:4px;border:1px solid #1a2540;">'
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
        return "#10b981" if num >= 0 else "#ef4444"
    except Exception:
        return "#e2e8f0"


def _trend_color(val):
    v = str(val).lower()
    if v == "rising":  return "#10b981"
    if v == "falling": return "#ef4444"
    return "#f59e0b"


def _action_color(val):
    v = str(val).upper()
    if v in ("BUY", "INIT_BUY"):  return "#10b981"
    if v == "SELL":                return "#ef4444"
    return "#f59e0b"


# ─── TOP TICKER TAPE ──────────────────────────────────────────────────────────
def render_ticker_tape():
    # Renders the top-of-page Bloomberg-style portfolio metrics bar
    pf = load_portfolio_state()
    tv = pf["total_value"]
    cash = pf["cash"]
    dpnl = pf["daily_pnl"]
    dpct = pf["daily_pnl_pct"]
    tret = pf["total_return_pct"]

    dpnl_color = "#10b981" if dpnl >= 0 else "#ef4444"
    tret_color = "#10b981" if tret >= 0 else "#ef4444"
    dpnl_sign  = "+" if dpnl >= 0 else ""
    tret_sign  = "+" if tret >= 0 else ""

    status_dot_color = "#10b981" if st.session_state.sim_started else "#f59e0b"

    tape_html = f"""
    <div style="
        background:#0d1526;
        border:1px solid #1a2540;
        border-left:3px solid #f59e0b;
        border-radius:4px;
        padding:0.65rem 1.4rem;
        margin-bottom:1.1rem;
        font-family:'IBM Plex Mono','Courier New',monospace;
        font-size:0.8rem;
        display:flex;
        flex-wrap:wrap;
        gap:2.2rem;
        align-items:center;
    ">
        <span style="display:flex;align-items:center;gap:0.5rem;">
            <span style="color:{status_dot_color};font-size:0.65rem;animation:pulse 2s infinite;">&#9679;</span>
            <span style="color:#f59e0b;font-weight:500;letter-spacing:2px;font-size:0.82rem;">PAPER TRADING TERMINAL</span>
        </span>
        <span style="color:#1a2540;">&#124;</span>
        <span>
            <span style="color:#4a5878;font-size:0.72rem;letter-spacing:1px;">PORTFOLIO&nbsp;</span>
            <span style="color:#e2e8f0;font-weight:500;">${tv:,.2f}</span>
        </span>
        <span>
            <span style="color:#4a5878;font-size:0.72rem;letter-spacing:1px;">CASH&nbsp;</span>
            <span style="color:#e2e8f0;">${cash:,.2f}</span>
        </span>
        <span>
            <span style="color:#4a5878;font-size:0.72rem;letter-spacing:1px;">DAILY P&amp;L&nbsp;</span>
            <span style="color:{dpnl_color};font-weight:500;">{dpnl_sign}${dpnl:,.2f}&nbsp;<span style="font-size:0.72rem;">({dpnl_sign}{dpct:.2f}%)</span></span>
        </span>
        <span>
            <span style="color:#4a5878;font-size:0.72rem;letter-spacing:1px;">TOTAL RETURN&nbsp;</span>
            <span style="color:{tret_color};font-weight:500;">{tret_sign}{tret:.2f}%</span>
        </span>
        <span>
            <span style="color:#4a5878;font-size:0.72rem;letter-spacing:1px;">SIM DATE&nbsp;</span>
            <span style="color:#f59e0b;">{st.session_state.current_date}</span>
        </span>
    </div>
    <style>
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.35; }}
    }}
    </style>
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
            '<div style="color:#f59e0b;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.8rem;font-weight:500;letter-spacing:2px;border-bottom:'
            '1px solid #1a2540;padding-bottom:0.5rem;margin-bottom:0.9rem;text-transform:uppercase;">'
            'Command Panel</div>',
            unsafe_allow_html=True
        )

        # Simulation date display
        st.markdown(
            f'<div style="color:#4a5878;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            f'font-size:0.76rem;margin-bottom:0.75rem;letter-spacing:1px;">'
            f'SIM DATE&nbsp;<span style="color:#f59e0b;">{st.session_state.current_date}</span></div>',
            unsafe_allow_html=True
        )

        st.markdown("---")

        # ── INIT PORTFOLIO ──
        if st.button("[ INIT PORTFOLIO ]", key="btn_init", use_container_width=True):
            _handle_init_portfolio()

        # ── CONFIRM MACRO ── (shown only after phase 1 complete, before phase 2)
        if st.session_state.macro_phase1_done and not st.session_state.macro_confirmed:
            st.markdown(
                '<div style="color:#f59e0b;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
                'font-size:0.72rem;margin-top:0.5rem;border-left:2px solid #f59e0b;padding-left:0.5rem;">'
                '&#9888; REVIEW MACRO ANALYSIS IN MACRO TAB<br>THEN CONFIRM BELOW</div>',
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
                f'<div style="color:#f59e0b;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
                f'font-size:0.72rem;letter-spacing:1px;margin-bottom:0.3rem;">'
                f'&#9670; {n} APPROVED TRADE(S) PENDING</div>',
                unsafe_allow_html=True
            )
            if st.button("[ EXECUTE TRADES ]", key="btn_execute", use_container_width=True):
                _handle_execute_trades()

        # ── RUN N DAYS ──
        st.markdown(
            '<div style="color:#4a5878;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.68rem;letter-spacing:1px;margin:0.5rem 0 0.3rem;text-transform:uppercase;">Auto-Run N Days</div>',
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
        status_color = "#10b981" if st.session_state.sim_started else "#f59e0b"
        status_label = "LIVE" if st.session_state.sim_started else "OFFLINE"
        last_run = st.session_state.last_run_time or "—"
        st.markdown(
            f'<div style="font-family:\'IBM Plex Mono\',\'Courier New\',monospace;font-size:0.72rem;color:#4a5878;line-height:1.8;">'
            f'STATUS&nbsp;<span style="color:{status_color};">&#9679; {status_label}</span><br>'
            f'LAST RUN&nbsp;<span style="color:#e2e8f0;">{last_run}</span>'
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
        '<h3 style="color:#f59e0b;letter-spacing:2px;font-weight:500;margin-bottom:0.75rem;">TRADING FLOOR</h3>',
        unsafe_allow_html=True
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        bsep("Macro Regime")
        result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")
        if result:
            narrative = result.get("regime_narrative", "—")
            terminal_text(narrative, color="#e2e8f0")
        else:
            terminal_text("NO MACRO DATA — RUN [ INIT PORTFOLIO ]", color="#4a5878")

    with col2:
        bsep("Proposed Trades")
        if st.session_state.proposed_trades:
            df_trades = pd.DataFrame(st.session_state.proposed_trades)
            render_terminal_table(df_trades)
        else:
            terminal_text("NO TRADES PROPOSED — RUN [ RUN AGENTS ]", color="#4a5878")

    st.markdown("<br>", unsafe_allow_html=True)
    bsep("Agent Reasoning Log")

    # ── APPROVED TRADES ──
    if st.session_state.approved_trades:
        st.markdown(
            '<div style="color:#10b981;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin-bottom:0.3rem;">'
            '&#9654; APPROVED TRADES</div>',
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
            '<div style="color:#ef4444;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin:0.6rem 0 0.3rem;">'
            '&#10005; REJECTED TRADES</div>',
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
            color_fns={"ACTION": lambda _: "#ef4444"},
        )

    # ── EXECUTION LOG ──
    if st.session_state.agent_log:
        st.markdown(
            '<div style="color:#4a5878;font-family:\'IBM Plex Mono\',\'Courier New\',monospace;'
            'font-size:0.72rem;letter-spacing:1px;font-weight:500;margin:0.6rem 0 0.3rem;">'
            '&#9632; EXECUTION LOG</div>',
            unsafe_allow_html=True,
        )
        terminal_text(st.session_state.agent_log)

    # ── Fallback when nothing to show ──
    if (not st.session_state.approved_trades
            and not st.session_state.rejected_trades
            and not st.session_state.agent_log):
        terminal_text("NO LOG ENTRIES — RUN [ ADVANCE DAY ] → [ RUN AGENTS ] → [ EXECUTE TRADES ]", color="#4a5878")


# ─── TAB 2: PORTFOLIO ─────────────────────────────────────────────────────────
def render_portfolio():
    st.markdown(
        '<h3 style="color:#f59e0b;letter-spacing:2px;font-weight:500;margin-bottom:0.75rem;">PORTFOLIO HOLDINGS</h3>',
        unsafe_allow_html=True
    )
    positions = db.get_positions()
    prices    = st.session_state.prices

    if not positions:
        terminal_text("NO POSITIONS — INITIALIZE PORTFOLIO FIRST", color="#4a5878")
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
    pnl_color = "#10b981" if total_pnl >= 0 else "#ef4444"

    st.markdown(
        f'<div style="font-family:\'IBM Plex Mono\',\'Courier New\',monospace;font-size:0.78rem;'
        f'border-top:1px solid #1a2540;padding-top:0.5rem;margin-top:0.5rem;color:#4a5878;">'
        f'<span style="color:#f59e0b;">TOTAL HOLDINGS</span> '
        f'<span style="color:#e2e8f0;">${total_mv:,.2f}</span>'
        f' &nbsp;|&nbsp; '
        f'<span style="color:#f59e0b;">TOTAL P&L</span> '
        f'<span style="color:{pnl_color};">'
        f'{"+" if total_pnl>=0 else ""}${total_pnl:,.2f} '
        f'({"+" if total_pnl_pct>=0 else ""}{total_pnl_pct:.2f}%)'
        f'</span></div>',
        unsafe_allow_html=True
    )

    # ── Portfolio Treemap Heatmap ──
    st.markdown("<br>", unsafe_allow_html=True)
    bsep("Position Heatmap")
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
                    [0.0, "#7f1d1d"], [0.25, "#ef4444"], [0.45, "#1e2a3a"],
                    [0.55, "#1e2a3a"], [0.75, "#10b981"], [1.0, "#064e3b"],
                ],
                cmid=0,
                colorbar=dict(
                    title=dict(text="P&L %", font=dict(color="#e2e8f0")),
                    tickfont=dict(color="#e2e8f0"),
                    ticksuffix="%",
                    bgcolor="#080d1a",
                    bordercolor="#1a2540",
                ),
                line=dict(color="#080d1a", width=2),
            ),
            text=tree_text,
            textfont=dict(family="IBM Plex Mono", size=12),
            textinfo="label",
            hovertemplate="%{text}<extra></extra>",
        ))
        fig_tree.update_layout(
            title=dict(text="HOLDINGS HEATMAP — SIZE = WEIGHT, COLOR = P&L",
                       font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#080d1a",
            font=dict(color="#e2e8f0", family="IBM Plex Mono"),
            height=420,
            margin=dict(l=10, r=10, t=40, b=10),
        )
        st.plotly_chart(fig_tree, use_container_width=True)

    # Recent transactions
    st.markdown("<br>", unsafe_allow_html=True)
    bsep("Recent Transactions")
    txns = db.get_transactions()[:20]
    if txns:
        df_txns = pd.DataFrame(txns)[["date", "action", "symbol", "shares", "price", "reason"]]
        df_txns["shares"] = df_txns["shares"].map(lambda x: f"{x:,.4f}")
        df_txns["price"]  = df_txns["price"].map(lambda x: f"${x:,.4f}")
        df_txns.columns   = ["DATE", "ACTION", "TICKER", "SHARES", "PRICE", "REASON"]
        render_terminal_table(df_txns, color_fns={"ACTION": _action_color})
    else:
        terminal_text("NO TRANSACTIONS YET", color="#4a5878")


# ─── TAB 3: PERFORMANCE ───────────────────────────────────────────────────────
def render_performance():
    st.markdown(
        '<h3 style="color:#f59e0b;letter-spacing:2px;font-weight:500;margin-bottom:0.75rem;">PERFORMANCE ANALYTICS</h3>',
        unsafe_allow_html=True
    )
    snapshots = db.get_daily_snapshots()

    if len(snapshots) < 2:
        terminal_text("INSUFFICIENT DATA — RUN SIMULATION FOR AT LEAST 2 DAYS", color="#4a5878")
        return

    df_snap = pd.DataFrame(snapshots)
    df_snap["date"] = pd.to_datetime(df_snap["date"])
    initial_equity  = df_snap["total_equity"].iloc[0]

    # Warn when all snapshots are identical (happens when running future-date
    # simulation before real market data exists for those dates)
    if df_snap["total_equity"].std() < 1.0:
        st.markdown(
            '<div style="background:#1a1500;border:1px solid #f59e0b;border-left:3px solid #f59e0b;'
            'border-radius:4px;padding:0.65rem 1rem;margin-bottom:0.8rem;font-family:\'IBM Plex Mono\','
            '\'Courier New\',monospace;font-size:0.74rem;color:#f59e0b;">'
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
        ret_color = "#10b981" if total_return >= 0 else "#ef4444"
        st.markdown(
            f'<div style="background:#0d1526;border:1px solid #1a2540;border-top:2px solid #f59e0b;'
            f'padding:1.1rem 1rem;text-align:center;border-radius:4px;">'
            f'<div style="color:#4a5878;font-size:0.68rem;letter-spacing:1.5px;margin-bottom:0.5rem;text-transform:uppercase;">Total Return</div>'
            f'<div style="color:{ret_color};font-size:1.4rem;font-weight:500;">'
            f'{"+"if total_return>=0 else ""}{total_return:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c2:
        dd_color = "#ef4444" if max_drawdown < -5 else "#f59e0b"
        st.markdown(
            f'<div style="background:#0d1526;border:1px solid #1a2540;border-top:2px solid #f59e0b;'
            f'padding:1.1rem 1rem;text-align:center;border-radius:4px;">'
            f'<div style="color:#4a5878;font-size:0.68rem;letter-spacing:1.5px;margin-bottom:0.5rem;text-transform:uppercase;">Max Drawdown</div>'
            f'<div style="color:{dd_color};font-size:1.4rem;font-weight:500;">'
            f'{max_drawdown:.2f}%</div></div>',
            unsafe_allow_html=True
        )
    with c3:
        sh_color = "#10b981" if sharpe > 1 else ("#f59e0b" if sharpe > 0 else "#ef4444")
        st.markdown(
            f'<div style="background:#0d1526;border:1px solid #1a2540;border-top:2px solid #f59e0b;'
            f'padding:1.1rem 1rem;text-align:center;border-radius:4px;">'
            f'<div style="color:#4a5878;font-size:0.68rem;letter-spacing:1.5px;margin-bottom:0.5rem;text-transform:uppercase;">Sharpe Ratio</div>'
            f'<div style="color:{sh_color};font-size:1.4rem;font-weight:500;">'
            f'{sharpe:.2f}</div></div>',
            unsafe_allow_html=True
        )
    with c4:
        wr_color = "#10b981" if win_rate > 50 else "#ef4444"
        st.markdown(
            f'<div style="background:#0d1526;border:1px solid #1a2540;border-top:2px solid #f59e0b;'
            f'padding:1.1rem 1rem;text-align:center;border-radius:4px;">'
            f'<div style="color:#4a5878;font-size:0.68rem;letter-spacing:1.5px;margin-bottom:0.5rem;text-transform:uppercase;">Win Rate</div>'
            f'<div style="color:{wr_color};font-size:1.4rem;font-weight:500;">'
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
        line=dict(color="#10b981", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df_snap["date"],
        y=[initial_equity] * len(df_snap),
        mode="lines",
        name="Initial Capital",
        line=dict(color="#f59e0b", width=1, dash="dot"),
    ))
    fig.update_layout(
        title=dict(text="EQUITY CURVE", font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
        paper_bgcolor="#080d1a",
        plot_bgcolor="#0d1526",
        font=dict(color="#e2e8f0", family="IBM Plex Mono"),
        xaxis=dict(gridcolor="#1a2540", color="#4a5878", showgrid=True),
        yaxis=dict(gridcolor="#1a2540", color="#4a5878", showgrid=True,
                   tickformat="$,.0f", autorange=True, rangemode="normal"),
        legend=dict(bgcolor="#0d1526", bordercolor="#1a2540", font=dict(color="#e2e8f0")),
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
        line=dict(color="#ef4444", width=1.5),
        fill="tozeroy",
        fillcolor="rgba(239,68,68,0.08)",
    ))
    fig2.update_layout(
        title=dict(text="DRAWDOWN (%)", font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
        paper_bgcolor="#080d1a",
        plot_bgcolor="#0d1526",
        font=dict(color="#e2e8f0", family="IBM Plex Mono"),
        xaxis=dict(gridcolor="#1a2540", color="#4a5878"),
        yaxis=dict(gridcolor="#1a2540", color="#4a5878", tickformat=".2f"),
        height=250,
        margin=dict(l=20, r=20, t=40, b=20),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── ETF Correlation Matrix (FX-matrix style) ──
    st.markdown("<br>", unsafe_allow_html=True)
    bsep("ETF Correlation Matrix")
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
                        [0.0, "#7f1d1d"], [0.25, "#ef4444"],
                        [0.5, "#0d1526"],
                        [0.75, "#10b981"], [1.0, "#064e3b"],
                    ],
                    zmin=-1, zmax=1,
                    text=corr.values.round(2),
                    texttemplate="%{text}",
                    textfont=dict(size=10, color="#e2e8f0", family="IBM Plex Mono"),
                    colorbar=dict(
                        title=dict(text="Corr", font=dict(color="#e2e8f0")),
                        tickfont=dict(color="#e2e8f0"),
                        bgcolor="#080d1a", bordercolor="#1a2540",
                    ),
                    hovertemplate="%{x} vs %{y}: %{z:.3f}<extra></extra>",
                ))
                fig_corr.update_layout(
                    title=dict(text="RETURN CORRELATION MATRIX",
                               font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
                    paper_bgcolor="#080d1a",
                    plot_bgcolor="#0d1526",
                    font=dict(color="#e2e8f0", family="IBM Plex Mono"),
                    xaxis=dict(color="#4a5878", tickangle=-45),
                    yaxis=dict(color="#4a5878", autorange="reversed"),
                    height=500,
                    margin=dict(l=20, r=20, t=40, b=20),
                )
                st.plotly_chart(fig_corr, use_container_width=True)
            else:
                terminal_text("INSUFFICIENT HELD TICKERS FOR CORRELATION MATRIX", color="#4a5878")
        else:
            terminal_text("INSUFFICIENT PRICE HISTORY FOR CORRELATION MATRIX", color="#4a5878")
    except Exception as e:
        terminal_text(f"CORRELATION MATRIX ERROR: {e}", color="#ef4444")

    # ── Daily snapshots table ──
    bsep("Daily Snapshots")
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
        '<h3 style="color:#f59e0b;letter-spacing:2px;font-weight:500;margin-bottom:0.75rem;">MACRO DASHBOARD</h3>',
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
        bsep("Factor Drift: Target vs Actual")

        # Grouped bar chart: target vs actual
        fig_drift = go.Figure()
        fig_drift.add_trace(go.Bar(
            name="Target",
            x=[factor_names[f] for f in factors],
            y=target_vals,
            marker_color="#1a2540",
            marker_line=dict(color="#f59e0b", width=1),
            text=[f"{v:.1f}%" for v in target_vals],
            textposition="outside",
            textfont=dict(color="#f59e0b", size=10, family="IBM Plex Mono"),
        ))
        fig_drift.add_trace(go.Bar(
            name="Actual",
            x=[factor_names[f] for f in factors],
            y=actual_vals,
            marker_color=["#10b981" if a >= t else "#ef4444" for a, t in zip(actual_vals, target_vals)],
            text=[f"{v:.1f}%" for v in actual_vals],
            textposition="outside",
            textfont=dict(color="#e2e8f0", size=10, family="IBM Plex Mono"),
        ))
        fig_drift.add_hline(y=70, line_dash="dot", line_color="#e2e8f0",
                            annotation_text="70% CAP", annotation_font_color="#e2e8f0",
                            annotation_font_size=10)
        fig_drift.update_layout(
            barmode="group",
            title=dict(text="FACTOR ALLOCATION: TARGET vs ACTUAL",
                       font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#080d1a",
            plot_bgcolor="#0d1526",
            font=dict(color="#e2e8f0", family="IBM Plex Mono"),
            xaxis=dict(gridcolor="#1a2540", color="#4a5878"),
            yaxis=dict(gridcolor="#1a2540", color="#4a5878", ticksuffix="%", range=[0, 100]),
            legend=dict(bgcolor="#0d1526", bordercolor="#1a2540", font=dict(color="#e2e8f0", size=9)),
            height=380,
            margin=dict(l=20, r=20, t=40, b=20),
        )
        st.plotly_chart(fig_drift, use_container_width=True)

        # Delta summary cards
        delta_html = '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:1rem;">'
        for f in factors:
            d = actual_sub[f] - target_sub[f]
            arrow = "+" if d >= 0 else ""
            color = "#10b981" if abs(d) < 3 else ("#f59e0b" if abs(d) < 7 else "#ef4444")
            delta_html += (
                f'<div style="background:#0d1526;border:1px solid {color};border-radius:4px;'
                f'padding:7px 14px;text-align:center;min-width:84px;">'
                f'<div style="color:#4a5878;font-size:0.63rem;letter-spacing:1.2px;text-transform:uppercase;">{factor_names[f]}</div>'
                f'<div style="color:{color};font-size:1rem;font-weight:500;margin-top:2px;">{arrow}{d:.1f}%</div>'
                f'</div>'
            )
        delta_html += '</div>'
        st.markdown(delta_html, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    result = st.session_state.get("macro_full_result") or st.session_state.get("macro_phase1_result")

    if not result:
        terminal_text(
            "NO MACRO DATA LOADED\n\nClick [ INIT PORTFOLIO ] in the sidebar to fetch FRED indicators.",
            color="#4a5878"
        )
        return

    # ── Macro Summary Table ──
    bsep("FRED Macro Indicators")
    summary_rows = result.get("summary_rows", [])
    if summary_rows:
        df_macro = pd.DataFrame(summary_rows)[["indicator", "value", "unit", "trend", "interpretation"]]
        df_macro.columns = ["INDICATOR", "VALUE", "UNIT", "TREND", "INTERPRETATION"]
        render_terminal_table(df_macro, color_fns={"TREND": _trend_color})

    # ── Regime narrative ──
    st.markdown("<br>", unsafe_allow_html=True)
    narrative = result.get("regime_narrative", "")
    if narrative:
        bsep("Macro Regime Narrative")
        terminal_text(narrative, color="#e2e8f0")

    # ── Axis Scoring (Phase 2) ──
    axis_scores = result.get("axis_scores", {})
    if axis_scores:
        st.markdown('<div style="margin-top:0.75rem;"></div>', unsafe_allow_html=True)
        bsep("Axis Scoring Breakdown")
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
        st.markdown('<div style="margin-top:0.75rem;"></div>', unsafe_allow_html=True)
        bsep("Strategic Allocation")
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
                    "#10b981", "#3b82f6", "#f59e0b", "#ef4444",
                    "#06b6d4", "#1d4ed8", "#ea580c", "#991b1b",
                    "#34d399", "#60a5fa", "#fbbf24", "#f87171",
                    "#064e3b", "#1e3a8a", "#9a3412", "#450a0a",
                ],
                line=dict(color="#080d1a", width=1),
            ),
            textfont=dict(color="#e2e8f0", family="IBM Plex Mono", size=10),
            textinfo="label+percent",
        )])
        fig.update_layout(
            title=dict(text="BUCKET ALLOCATION", font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#080d1a",
            plot_bgcolor="#080d1a",
            font=dict(color="#e2e8f0", family="IBM Plex Mono"),
            legend=dict(bgcolor="#0d1526", font=dict(color="#e2e8f0", size=9), bordercolor="#1a2540"),
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
        first_colors  = ["#10b981", "#06b6d4", "#ef4444", "#34d399"]
        second_colors = ["#f59e0b", "#f97316", "#3b82f6", "#fbbf24"]

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Defensive / Growth / Hi-β / US",
            x=pair_labels,
            y=[sub_totals[s] for s in first_subs],
            marker_color=first_colors,
            text=[f"{sub}: {sub_totals[sub]:.1f}%" for sub in first_subs],
            textposition="inside",
            textfont=dict(color="#e2e8f0", size=10, family="IBM Plex Mono"),
        ))
        fig2.add_trace(go.Bar(
            name="Cyclical / Value / Lo-β / EM",
            x=pair_labels,
            y=[sub_totals[s] for s in second_subs],
            marker_color=second_colors,
            text=[f"{sub}: {sub_totals[sub]:.1f}%" for sub in second_subs],
            textposition="inside",
            textfont=dict(color="#080d1a", size=10, family="IBM Plex Mono"),
        ))
        fig2.add_hline(y=70, line_dash="dot", line_color="#e2e8f0",
                       annotation_text="70% CAP", annotation_font_color="#e2e8f0")
        fig2.update_layout(
            barmode="stack",
            title=dict(text="FACTOR EXPOSURE vs. 70% SUB-STRATEGY CAP",
                       font=dict(color="#f59e0b", family="IBM Plex Mono", size=13)),
            paper_bgcolor="#080d1a",
            plot_bgcolor="#0d1526",
            font=dict(color="#e2e8f0", family="IBM Plex Mono"),
            xaxis=dict(gridcolor="#1a2540", color="#4a5878"),
            yaxis=dict(gridcolor="#1a2540", color="#4a5878", range=[0, 110], ticksuffix="%"),
            legend=dict(bgcolor="#0d1526", bordercolor="#1a2540", font=dict(color="#e2e8f0", size=9)),
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
        "TRADING FLOOR",
        "PORTFOLIO",
        "PERFORMANCE",
        "MACRO",
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
