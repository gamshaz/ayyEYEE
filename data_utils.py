import os
import pandas as pd
import yfinance as yf
from fredapi import Fred
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")

# FRED macro data: fetch January 2023 to present for regime analysis
MACRO_START = "2023-01-01"
MACRO_END   = datetime.today().strftime("%Y-%m-%d")

# Price simulation: January 2026 → March 2026 (current sim window)
# Warmup data: December 1–31 2025 (ensures indicators populated from sim day 1)

# All ETF tickers used in the universe
ALL_TICKERS = [
    "XBI", "EMQQ", "XLV", "INDA", "SDY", "EELV", "SPLV",
    "SMH", "EEM", "RSP", "CQQQ", "XLE", "AVES", "XLI", "FEMS"
]


def get_fred_client():
    # Returns an authenticated FRED API client
    if not FRED_API_KEY:
        raise ValueError("FRED_API_KEY not found in environment. Check your .env file.")
    return Fred(api_key=FRED_API_KEY)


def get_etf_price(ticker: str, as_of_date: str = None) -> float:
    """
    Fetches the closing price of an ETF.
    If as_of_date is given, returns the last available close on or before that date.
    Never uses future data — respects the as_of_date ceiling strictly.
    """
    try:
        if as_of_date:
            end = (datetime.strptime(as_of_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            start = (datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=10)).strftime("%Y-%m-%d")
            df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
            # ANTI-LOOKAHEAD: never use prices beyond current simulation date
            df = df[df.index <= as_of_date]
        else:
            df = yf.download(ticker, period="5d", progress=False, auto_adjust=True)

        if df.empty:
            return None
        return float(df["Close"].iloc[-1])
    except Exception as e:
        print(f"[data_utils] Error fetching price for {ticker}: {e}")
        return None


def get_etf_prices_bulk(tickers: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Downloads adjusted close prices for multiple tickers over a date range.
    Returns a DataFrame with dates as index and tickers as columns.

    IMPORTANT: end_date is exclusive in yfinance. Always pass end_date as
    (simulation_date + 1 day) and then apply the anti-lookahead filter below.
    """
    try:
        raw = yf.download(tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            closes = raw[["Close"]]
            closes.columns = tickers
        return closes.dropna(how="all")
    except Exception as e:
        print(f"[data_utils] Error fetching bulk prices: {e}")
        return pd.DataFrame()


def get_price_history_with_warmup(as_of_date: str, warmup_start: str = "2025-12-01") -> pd.DataFrame:
    """
    Fetches full price history from warmup_start through as_of_date for all ETFs.
    Used by the tactical agent to ensure indicators are populated from Jan 2026 day 1.

    ANTI-LOOKAHEAD: prices are strictly filtered to ≤ as_of_date.
    """
    end_date = (datetime.strptime(as_of_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    df = get_etf_prices_bulk(ALL_TICKERS, start_date=warmup_start, end_date=end_date)
    if not df.empty:
        # ANTI-LOOKAHEAD: never use prices beyond current simulation date
        df = df[df.index <= as_of_date]
    return df


def get_all_current_prices(as_of_date: str = None) -> dict:
    # Fetches latest price for every ETF in the universe, returning {ticker: price}
    prices = {}
    for ticker in ALL_TICKERS:
        price = get_etf_price(ticker, as_of_date)
        if price is not None:
            prices[ticker] = price
    return prices


def get_fred_series(series_id: str, start_date: str = MACRO_START, end_date: str = MACRO_END) -> pd.Series:
    # Fetches a single FRED time series and returns it as a Pandas Series
    try:
        fred = get_fred_client()
        series = fred.get_series(series_id, observation_start=start_date, observation_end=end_date)
        return series.dropna()
    except Exception as e:
        print(f"[data_utils] Error fetching FRED series {series_id}: {e}")
        return pd.Series(dtype=float)


def compute_yoy_change(series: pd.Series) -> pd.Series:
    # Computes year-over-year percentage change for a monthly series
    return series.pct_change(periods=12) * 100


def compute_trend(series: pd.Series, lookback: int = 6) -> str:
    """
    Returns 'rising', 'falling', or 'stable' based on the last N observations.
    Uses linear slope direction with a 0.5% threshold for stability.
    """
    if series.empty or len(series) < 2:
        return "stable"
    recent = series.iloc[-lookback:] if len(series) >= lookback else series
    first_val = recent.iloc[0]
    last_val = recent.iloc[-1]
    if first_val == 0:
        return "stable"
    change_pct = ((last_val - first_val) / abs(first_val)) * 100
    if change_pct > 0.5:
        return "rising"
    elif change_pct < -0.5:
        return "falling"
    return "stable"


def get_macro_indicators() -> dict:
    """
    Fetches all required macro indicators from FRED.
    Returns a dict with indicator name -> {value, series, trend, raw_series}.
    Time range: January 2023 to latest available.
    """
    indicators = {}

    # --- Yield Curve: 10yr minus 3m spread ---
    gs10 = get_fred_series("GS10")
    tb3ms = get_fred_series("TB3MS")
    if not gs10.empty and not tb3ms.empty:
        combined = pd.concat([gs10, tb3ms], axis=1, join="inner")
        combined.columns = ["GS10", "TB3MS"]
        spread = combined["GS10"] - combined["TB3MS"]
        indicators["yield_curve_spread"] = {
            "label": "Yield Curve (10yr - 3m)",
            "series": spread,
            "value": round(float(spread.iloc[-1]), 3),
            "unit": "pct pts",
            "trend": compute_trend(spread),
        }

    # --- CPI Headline YoY % ---
    cpi = get_fred_series("CPIAUCSL")
    if not cpi.empty:
        cpi_yoy = compute_yoy_change(cpi)
        cpi_yoy = cpi_yoy.dropna()
        indicators["cpi_yoy"] = {
            "label": "CPI Headline YoY",
            "series": cpi_yoy,
            "value": round(float(cpi_yoy.iloc[-1]), 2),
            "unit": "%",
            "trend": compute_trend(cpi_yoy),
        }

    # --- Unemployment Gap: UR minus NAIRU ---
    unrate = get_fred_series("UNRATE")
    nrou = get_fred_series("NROU")
    if not unrate.empty and not nrou.empty:
        combined = pd.concat([unrate, nrou], axis=1, join="inner")
        combined.columns = ["UNRATE", "NROU"]
        ur_gap = combined["UNRATE"] - combined["NROU"]
        indicators["unemployment_gap"] = {
            "label": "UR minus NAIRU",
            "series": ur_gap,
            "value": round(float(ur_gap.iloc[-1]), 2),
            "unit": "pct pts",
            "trend": compute_trend(ur_gap),
        }

    # --- Output Gap: deviation from potential GDP ---
    gdp = get_fred_series("GDP")
    gdppot = get_fred_series("GDPPOT")
    if not gdp.empty and not gdppot.empty:
        # Align quarterly GDP to potential GDP
        combined = pd.concat([gdp, gdppot], axis=1, join="inner")
        combined.columns = ["GDP", "GDPPOT"]
        output_gap = ((combined["GDP"] - combined["GDPPOT"]) / combined["GDPPOT"]) * 100
        indicators["output_gap"] = {
            "label": "Output Gap (% of Potential)",
            "series": output_gap,
            "value": round(float(output_gap.iloc[-1]), 2),
            "unit": "%",
            "trend": compute_trend(output_gap),
        }

    # --- S&P 500 EPS Trend ---
    eps = get_fred_series("SPASTT01USQ657N")
    if not eps.empty:
        indicators["sp500_eps"] = {
            "label": "S&P 500 EPS (Index)",
            "series": eps,
            "value": round(float(eps.iloc[-1]), 2),
            "unit": "index",
            "trend": compute_trend(eps),
        }
    else:
        # Fallback: try corporate profits series
        corp_profits = get_fred_series("CP")
        if not corp_profits.empty:
            indicators["sp500_eps"] = {
                "label": "Corporate Profits (Fallback)",
                "series": corp_profits,
                "value": round(float(corp_profits.iloc[-1]), 2),
                "unit": "B USD",
                "trend": compute_trend(corp_profits),
            }

    # --- Federal Funds Rate (additional context) ---
    fed_rate = get_fred_series("FEDFUNDS")
    if not fed_rate.empty:
        indicators["fed_funds_rate"] = {
            "label": "Fed Funds Rate",
            "series": fed_rate,
            "value": round(float(fed_rate.iloc[-1]), 2),
            "unit": "%",
            "trend": compute_trend(fed_rate),
        }

    return indicators


def get_portfolio_holdings_value(positions: list, prices: dict) -> float:
    # Sums up current market value of all positions using latest prices
    total = 0.0
    for pos in positions:
        ticker = pos["symbol"]
        shares = pos["shares"]
        price = prices.get(ticker, pos.get("current_price", 0))
        total += shares * price
    return total
