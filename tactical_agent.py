"""
tactical_agent.py - Tactical / Daily Trading Agent (PLACEHOLDER)

This module proposes intraday trades based on technical signals.
Currently returns empty trade lists. Signal computation methods
are stubbed and marked for future implementation.

FUTURE IMPLEMENTATION AREAS are clearly marked with # TODO comments.
"""

import pandas as pd
from typing import List, Dict, Any


def compute_signals(prices_df: pd.DataFrame) -> dict:
    """
    Computes technical trading signals from historical price data.
    Returns a dict: {ticker: signal_strength (float, -1.0 to 1.0)}

    Positive values = bullish, negative = bearish, 0 = neutral.

    prices_df: DataFrame with dates as index, tickers as columns.

    Currently returns empty dict — indicators to be implemented below.
    """
    signals = {}

    if prices_df.empty:
        return signals

    for ticker in prices_df.columns:
        price_series = prices_df[ticker].dropna()
        if len(price_series) < 20:
            continue

        ticker_signal = 0.0

        # TODO: Implement MA Crossover signal
        # short_ma = price_series.rolling(window=10).mean()
        # long_ma = price_series.rolling(window=30).mean()
        # if short_ma.iloc[-1] > long_ma.iloc[-1]:
        #     ticker_signal += 0.33  # bullish crossover
        # elif short_ma.iloc[-1] < long_ma.iloc[-1]:
        #     ticker_signal -= 0.33  # bearish crossover

        # TODO: Implement RSI signal
        # delta = price_series.diff()
        # gain = delta.clip(lower=0).rolling(14).mean()
        # loss = (-delta.clip(upper=0)).rolling(14).mean()
        # rs = gain / loss
        # rsi = 100 - (100 / (1 + rs))
        # rsi_val = rsi.iloc[-1]
        # if rsi_val < 30:
        #     ticker_signal += 0.33  # oversold — buy signal
        # elif rsi_val > 70:
        #     ticker_signal -= 0.33  # overbought — sell signal

        # TODO: Implement Momentum signal (12-1 month)
        # if len(price_series) >= 252:
        #     momentum = (price_series.iloc[-21] - price_series.iloc[-252]) / price_series.iloc[-252]
        #     ticker_signal += 0.33 * (1 if momentum > 0 else -1)

        # TODO: Implement Bollinger Band signal
        # TODO: Implement MACD signal
        # TODO: Implement Volume-weighted momentum

        signals[ticker] = round(ticker_signal, 4)

    return signals


def rank_signals(signals: dict) -> list:
    """
    Sorts signals by absolute strength and returns the top 3 only.
    Only the top 3 signals by strength are acted on per day —
    maximum 3 trades per day from this agent.

    Returns a list of (ticker, signal_strength) tuples, strongest first.
    """
    if not signals:
        return []

    # Sort by absolute signal strength, descending
    ranked = sorted(signals.items(), key=lambda x: abs(x[1]), reverse=True)

    # Enforce top-3 cap
    return ranked[:3]


def propose_trades(
    current_date: str,
    positions: List[Dict[str, Any]],
    prices: Dict[str, float],
    portfolio_value: float,
    prices_history: pd.DataFrame = None,
) -> List[Dict[str, Any]]:
    """
    Main entry point for the tactical agent.
    Generates a list of proposed trades for the current trading day.

    Args:
        current_date:    ISO date string (YYYY-MM-DD)
        positions:       List of current position dicts from database
        prices:          Dict of {ticker: current_price}
        portfolio_value: Total portfolio value (cash + holdings)
        prices_history:  DataFrame of historical prices (dates x tickers)

    Returns:
        List of proposed trade dicts:
        {
            "symbol":          str,
            "action":          "BUY" or "SELL",
            "shares":          float,
            "signal_strength": float (-1.0 to 1.0),
            "reason":          str,
        }

    Currently returns empty list — no signals implemented yet.
    """
    proposed_trades = []

    # Step 1: Compute raw signals from price history
    # TODO: Pass in meaningful price history once data pipeline is wired up
    signals = compute_signals(prices_history if prices_history is not None else pd.DataFrame())

    # Step 2: Rank and cap at top 3 signals
    top_signals = rank_signals(signals)

    # Step 3: Convert signals into trade proposals
    # TODO: Convert signal strength into share quantities based on target weight shifts
    # TODO: Check current position vs. target allocation before proposing
    # TODO: Implement rebalancing logic when positions drift from target weights
    for ticker, strength in top_signals:
        if abs(strength) < 0.1:
            # Ignore very weak signals — noise threshold
            continue

        action = "BUY" if strength > 0 else "SELL"
        current_price = prices.get(ticker, 0)
        if current_price <= 0:
            continue

        # TODO: Size trades based on signal strength and portfolio weight limits
        # For now, placeholder shares = 0 so no actual capital moves
        proposed_trades.append({
            "symbol":          ticker,
            "action":          action,
            "shares":          0,  # placeholder
            "signal_strength": strength,
            "reason":          f"Placeholder signal ({strength:+.2f}) — implement indicators",
        })

    return proposed_trades
