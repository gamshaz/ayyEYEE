"""
tactical_agent.py - Tactical / Daily Trading Agent

Generates daily trade proposals using three technical indicators:
  - 3-day / 10-day MA crossover  (weight ±2)
  - RSI 14-day                   (weight ±1)
  - Bollinger Bands 30-day/1.5σ  (weight ±3)

Max signal score per ETF: ±6.
Top 3 ETFs by absolute score are acted on each day.
Portfolio stays ≤ 2% cash at all times (enforced via cash management logic
in propose_trades and post-trade by execution_agent.deploy_excess_cash).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd

import data_utils

# ── Warmup window ─────────────────────────────────────────────────────────────
# Dec 2025 ensures MA10, RSI-14, and BB-30 are fully populated from Jan 2026 day 1
WARMUP_START = "2025-12-01"

# ── Signal weights ─────────────────────────────────────────────────────────────
WEIGHT_MA  = 2   # MA crossover
WEIGHT_RSI = 1   # RSI overbought / oversold
WEIGHT_BB  = 3   # Bollinger Band cross

# ── Trade size table: abs(score) → % of portfolio ─────────────────────────────
SCORE_TO_PCT: dict[int, float] = {6: 8.0, 5: 6.0, 4: 4.0, 3: 4.0, 2: 2.0, 1: 2.0}

# ── Max cash buffer ────────────────────────────────────────────────────────────
MAX_CASH_PCT = 0.02   # 2% of portfolio value


# ─── Price history ─────────────────────────────────────────────────────────────

def _fetch_price_history(current_date: str) -> pd.DataFrame:
    """
    Fetches ETF price history from WARMUP_START through current_date.
    ANTI-LOOKAHEAD: end_date is set to current_date+1 for yfinance (exclusive),
    then strictly filtered to ≤ current_date so future prices are never used.
    """
    # yfinance end is exclusive, so add 1 day
    end_dt = datetime.strptime(current_date, "%Y-%m-%d") + timedelta(days=1)
    end_date = end_dt.strftime("%Y-%m-%d")

    df = data_utils.get_etf_prices_bulk(
        data_utils.ALL_TICKERS,
        start_date=WARMUP_START,
        end_date=end_date,
    )

    if not df.empty:
        # ANTI-LOOKAHEAD: never use prices beyond current simulation date
        df = df[df.index <= current_date]

    return df


# ─── Technical indicators ──────────────────────────────────────────────────────

def _compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """RSI using Wilder exponential smoothing (EWM). Standard implementation."""
    delta = series.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    # Avoid division by zero
    rs    = gain / loss.where(loss != 0, other=1e-9)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_signals(prices_df: pd.DataFrame) -> dict[str, dict]:
    """
    Computes MA crossover, RSI, and Bollinger Band signals for every ticker
    that has sufficient history.

    A crossover means today's relationship CHANGED vs yesterday — not merely
    that one MA is above the other.

    Returns:
        {
          ticker: {
            "score":        int,          # negative = bearish, positive = bullish
            "rsi":          float,        # latest RSI value (for fallback ranking)
            "reason_parts": list[str],    # human-readable breakdown
          }
        }
    Score 0 means no actionable signal today (included so RSI is available for
    cash-management fallback).
    """
    results: dict[str, dict] = {}

    if prices_df.empty or len(prices_df) < 2:
        return results

    for ticker in prices_df.columns:
        series = prices_df[ticker].dropna()

        # Need at least MA10 + 1 prior day
        if len(series) < 11:
            continue

        score: int = 0
        reasons: list[str] = []

        # ── MA crossover (weight ±2) ───────────────────────────────────────
        ma3  = series.rolling(3).mean()
        ma10 = series.rolling(10).mean()

        ma3_t, ma3_y   = ma3.iloc[-1],  ma3.iloc[-2]
        ma10_t, ma10_y = ma10.iloc[-1], ma10.iloc[-2]

        if pd.notna(ma3_t) and pd.notna(ma10_t) and pd.notna(ma3_y) and pd.notna(ma10_y):
            if (ma3_t > ma10_t) and (ma3_y <= ma10_y):
                score += WEIGHT_MA
                reasons.append(f"MA3 crossed above MA10 (+{WEIGHT_MA})")
            elif (ma3_t < ma10_t) and (ma3_y >= ma10_y):
                score -= WEIGHT_MA
                reasons.append(f"MA3 crossed below MA10 (-{WEIGHT_MA})")

        # ── RSI 14-day (weight ±1) ─────────────────────────────────────────
        rsi_series = _compute_rsi(series, 14)
        rsi_val    = float(rsi_series.iloc[-1]) if len(rsi_series) > 0 and pd.notna(rsi_series.iloc[-1]) else 50.0

        if rsi_val > 60:
            score -= WEIGHT_RSI
            reasons.append(f"RSI={rsi_val:.0f} overbought (-{WEIGHT_RSI})")
        elif rsi_val < 40:
            score += WEIGHT_RSI
            reasons.append(f"RSI={rsi_val:.0f} oversold (+{WEIGHT_RSI})")

        # ── Bollinger Bands 30-day / 1.5σ (weight ±3) ─────────────────────
        # Need 30-day window + 1 prior day
        if len(series) >= 31:
            bb_mean = series.rolling(30).mean()
            bb_std  = series.rolling(30).std()
            upper   = bb_mean + 1.5 * bb_std
            lower   = bb_mean - 1.5 * bb_std

            px_t, px_y = series.iloc[-1], series.iloc[-2]
            up_t, up_y = upper.iloc[-1], upper.iloc[-2]
            lo_t, lo_y = lower.iloc[-1], lower.iloc[-2]

            if pd.notna(up_t) and pd.notna(lo_t) and pd.notna(up_y) and pd.notna(lo_y):
                if px_t > up_t and px_y <= up_y:
                    score -= WEIGHT_BB
                    reasons.append(f"price crossed above upper BB (-{WEIGHT_BB})")
                elif px_t < lo_t and px_y >= lo_y:
                    score += WEIGHT_BB
                    reasons.append(f"price crossed below lower BB (+{WEIGHT_BB})")

        results[ticker] = {"score": score, "rsi": rsi_val, "reason_parts": reasons}

    return results


# ─── Trade sizing ──────────────────────────────────────────────────────────────

def _pct_for_score(score: int) -> float:
    """Maps abs(score) to % of portfolio to trade."""
    return SCORE_TO_PCT.get(abs(score), 2.0)


def _to_shares(pct: float, portfolio_value: float, price: float) -> int:
    """Converts a % of portfolio to a whole-share count (minimum 1)."""
    if price <= 0:
        return 0
    return max(1, int((pct / 100.0) * portfolio_value / price))


# ─── Main entry point ──────────────────────────────────────────────────────────

def propose_trades(
    current_date: str,
    positions: list[dict[str, Any]],
    prices: dict[str, float],
    portfolio_value: float,
) -> list[dict[str, Any]]:
    """
    Proposes up to 3 signal-based trades plus optional cash-management trades.

    Flow:
      1. Fetch price history (Dec 2025 warmup → current_date, anti-lookahead)
      2. Compute MA, RSI, BB signals for all tickers
      3. Rank by abs(score); top 3 non-zero scores are actionable
      4. If all top 3 are BUY but cash is insufficient → add forced sell
      5. Build SELL trades (size by score, capped at shares held)
      6. Build BUY trades (size by score, capped by available cash)
      7. If all top 3 were SELL → add reinvestment buy from proceeds
      8. Return all proposed trades (risk_agent validates and caps at 3)

    Each trade dict:
        {"symbol", "action", "shares", "signal_strength", "reason"}
    """
    # 1. Fetch price history (WARMUP_START → current_date)
    prices_df = _fetch_price_history(current_date)
    if prices_df.empty:
        return []

    # 2. Compute signals for all tickers
    signals = compute_signals(prices_df)
    if not signals:
        return []

    # 3. Rank all tickers by abs(score); extract top 3 with non-zero score
    ranked_all   = sorted(signals.items(), key=lambda x: abs(x[1]["score"]), reverse=True)
    top3         = [(t, d) for t, d in ranked_all if d["score"] != 0][:3]
    buy_signals  = [(t, d) for t, d in top3 if d["score"] > 0]
    sell_signals = [(t, d) for t, d in top3 if d["score"] < 0]

    if not top3:
        return []

    # 4. Current cash estimate from portfolio state
    pos_map        = {p["symbol"]: p["shares"] for p in positions}
    holdings_value = sum(pos_map.get(t, 0) * prices.get(t, 0) for t in pos_map)
    cash           = max(0.0, portfolio_value - holdings_value)

    proposed: list[dict[str, Any]] = []

    # ── Cash management: forced sell if all signals are BUY + insufficient cash ──
    if buy_signals and not sell_signals:
        needed = sum(
            _to_shares(_pct_for_score(d["score"]), portfolio_value, prices.get(t, 1))
            * prices.get(t, 0)
            for t, d in buy_signals
        )
        if cash < needed:
            # Find ETF with no buy signal today that has the strongest 5-day return
            buy_tickers = {t for t, _ in buy_signals}
            non_buy = [
                t for t in data_utils.ALL_TICKERS
                if t not in buy_tickers
                and t in prices_df.columns
                and pos_map.get(t, 0) > 0
            ]
            if len(prices_df) >= 5 and non_buy:
                five_day_ret: dict[str, float] = {}
                for t in non_buy:
                    s = prices_df[t].dropna()
                    if len(s) >= 5 and s.iloc[-5] > 0:
                        five_day_ret[t] = (s.iloc[-1] - s.iloc[-5]) / s.iloc[-5]

                if five_day_ret:
                    forced_t = max(five_day_ret, key=five_day_ret.get)
                    f_price  = prices.get(forced_t, 0)
                    f_held   = pos_map.get(forced_t, 0)
                    if f_held > 0 and f_price > 0:
                        sell_amt = min(needed - cash, f_held * f_price)
                        sell_sh  = min(int(sell_amt / f_price), int(f_held))
                        if sell_sh > 0:
                            proposed.append({
                                "symbol":          forced_t,
                                "action":          "SELL",
                                "shares":          sell_sh,
                                "signal_strength": 0,
                                "reason":          "Forced sell to fund buy orders - strongest recent performer",
                            })
                            cash += sell_sh * f_price

    # ── Build SELL trades ──────────────────────────────────────────────────────
    for ticker, data in sell_signals:
        price = prices.get(ticker, 0)
        held  = pos_map.get(ticker, 0)
        if price <= 0 or held <= 0:
            continue
        sh = min(
            _to_shares(_pct_for_score(data["score"]), portfolio_value, price),
            int(held),
        )
        if sh <= 0:
            continue
        reason = "; ".join(data["reason_parts"]) if data["reason_parts"] else "Technical sell signal"
        proposed.append({
            "symbol":          ticker,
            "action":          "SELL",
            "shares":          sh,
            "signal_strength": data["score"],
            "reason":          reason,
        })
        cash += sh * price

    # ── Build BUY trades ───────────────────────────────────────────────────────
    for ticker, data in buy_signals:
        price = prices.get(ticker, 0)
        if price <= 0:
            continue
        sh   = _to_shares(_pct_for_score(data["score"]), portfolio_value, price)
        cost = sh * price
        if cost > cash:
            sh   = max(0, int(cash / price))
            cost = sh * price
        if sh <= 0:
            continue
        reason = "; ".join(data["reason_parts"]) if data["reason_parts"] else "Technical buy signal"
        proposed.append({
            "symbol":          ticker,
            "action":          "BUY",
            "shares":          sh,
            "signal_strength": data["score"],
            "reason":          reason,
        })
        cash -= cost

    # ── If all 3 signals were SELL, reinvest proceeds immediately ─────────────
    if sell_signals and not buy_signals and cash > 0:
        sell_tickers = {t for t, _ in sell_signals}

        # Prefer the highest-scored positive-signal ETF not in the sell list
        buy_candidates = [
            (t, d) for t, d in ranked_all
            if d["score"] > 0 and t not in sell_tickers
        ]
        if buy_candidates:
            reinvest_t = buy_candidates[0][0]
        else:
            # Fallback: lowest RSI (most oversold) not already being sold
            non_sell_rsi = {
                t: d["rsi"] for t, d in signals.items() if t not in sell_tickers
            }
            reinvest_t = min(non_sell_rsi, key=non_sell_rsi.get) if non_sell_rsi else None

        if reinvest_t and reinvest_t in prices:
            r_price = prices[reinvest_t]
            if r_price > 0:
                sh = max(1, int(cash * 0.95 / r_price))
                proposed.append({
                    "symbol":          reinvest_t,
                    "action":          "BUY",
                    "shares":          sh,
                    "signal_strength": 0,
                    "reason":          "Reinvestment of sell proceeds to maintain full investment",
                })

    return proposed
