"""
risk_agent.py - Risk Management Agent

Enforces portfolio-level risk constraints before any trade is executed.
All rejected trades are logged with a clear reason.

Constraints:
  1. No single position may exceed 40% of total portfolio value
  2. No short selling (shares cannot go negative)
  3. Maximum 3 trades per day (enforces the top-3 tactical signals rule)
  4. No buying more than available cash allows
"""

from typing import List, Dict, Any, Tuple


MAX_POSITION_PCT   = 0.40   # 40% max single position
MAX_TRADES_PER_DAY = 3      # hard cap on daily trade count


def _get_current_shares(positions: list, symbol: str) -> float:
    # Returns the current share count for a given ticker, or 0 if not held
    for pos in positions:
        if pos["symbol"] == symbol:
            return pos["shares"]
    return 0.0


def _get_current_market_value(positions: list, symbol: str, prices: dict) -> float:
    # Returns the current market value of a position using live prices
    shares = _get_current_shares(positions, symbol)
    price = prices.get(symbol, 0.0)
    return shares * price


def validate_trades(
    proposed_trades: List[Dict[str, Any]],
    positions: List[Dict[str, Any]],
    cash: float,
    portfolio_value: float,
    prices: Dict[str, float],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filters proposed trades through risk constraints.

    Args:
        proposed_trades: Output from tactical_agent.propose_trades()
        positions:       Current portfolio positions from DB
        cash:            Available cash balance
        portfolio_value: Total portfolio value (cash + holdings)
        prices:          Dict of {ticker: current_price}

    Returns:
        (approved_trades, rejected_trades)
        rejected_trades have an additional 'rejection_reason' key.
    """
    approved  = []
    rejected  = []

    if portfolio_value <= 0:
        # Cannot trade with zero or negative portfolio value
        for trade in proposed_trades:
            t = dict(trade)
            t["rejection_reason"] = "Portfolio value is zero or negative — cannot validate trades."
            rejected.append(t)
            _log_rejection(t)
        return approved, rejected

    remaining_cash = cash

    for trade in proposed_trades:
        t = dict(trade)
        symbol  = t.get("symbol", "")
        action  = t.get("action", "").upper()
        shares  = t.get("shares", 0)
        price   = prices.get(symbol, 0.0)

        # --- Guard: skip zero-share placeholder trades ---
        if shares <= 0:
            t["rejection_reason"] = f"Zero or negative share quantity ({shares}) — skipped."
            rejected.append(t)
            _log_rejection(t)
            continue

        # --- Guard: unknown price ---
        if price <= 0:
            t["rejection_reason"] = f"No valid price available for {symbol} (price={price})."
            rejected.append(t)
            _log_rejection(t)
            continue

        trade_value = shares * price

        if action == "BUY":
            # Check 1: sufficient cash
            if trade_value > remaining_cash:
                t["rejection_reason"] = (
                    f"Insufficient cash: trade costs ${trade_value:,.2f} "
                    f"but only ${remaining_cash:,.2f} available."
                )
                rejected.append(t)
                _log_rejection(t)
                continue

            # Check 2: position concentration after trade
            current_mv = _get_current_market_value(positions, symbol, prices)
            new_mv = current_mv + trade_value
            new_pct = new_mv / portfolio_value
            if new_pct > MAX_POSITION_PCT:
                t["rejection_reason"] = (
                    f"Position concentration breach: buying {shares} shares of {symbol} "
                    f"would bring position to {new_pct:.1%} of portfolio "
                    f"(limit: {MAX_POSITION_PCT:.0%})."
                )
                rejected.append(t)
                _log_rejection(t)
                continue

            # Passed — tentatively deduct cash so subsequent BUYs see the updated balance
            remaining_cash -= trade_value

        elif action == "SELL":
            # Check 3: no short selling
            current_shares = _get_current_shares(positions, symbol)
            if shares > current_shares:
                t["rejection_reason"] = (
                    f"Short sell rejected: attempting to sell {shares:.4f} shares of {symbol} "
                    f"but only {current_shares:.4f} held."
                )
                rejected.append(t)
                _log_rejection(t)
                continue

        else:
            t["rejection_reason"] = f"Unknown action '{action}' — must be BUY or SELL."
            rejected.append(t)
            _log_rejection(t)
            continue

        approved.append(t)

    # Check 4: enforce daily trade cap AFTER individual checks
    if len(approved) > MAX_TRADES_PER_DAY:
        # Keep the top-MAX_TRADES_PER_DAY by signal strength; reject the rest
        approved_sorted = sorted(approved, key=lambda x: abs(x.get("signal_strength", 0)), reverse=True)
        approved   = approved_sorted[:MAX_TRADES_PER_DAY]
        overflow   = approved_sorted[MAX_TRADES_PER_DAY:]
        for trade in overflow:
            t = dict(trade)
            t["rejection_reason"] = (
                f"Daily trade cap of {MAX_TRADES_PER_DAY} reached — "
                f"trade de-prioritized by signal strength."
            )
            rejected.append(t)
            _log_rejection(t)

    return approved, rejected


def _log_rejection(trade: dict):
    # Prints a structured rejection notice to stdout for the app log panel
    symbol  = trade.get("symbol", "?")
    action  = trade.get("action", "?")
    reason  = trade.get("rejection_reason", "Unknown reason")
    print(f"[risk_agent] REJECTED {action} {symbol}: {reason}")


def get_rejection_summary(rejected_trades: list) -> str:
    # Formats the rejection list as a readable multi-line string for the UI
    if not rejected_trades:
        return "No trades rejected."
    lines = ["REJECTED TRADES:"]
    lines.append("─" * 60)
    for t in rejected_trades:
        lines.append(
            f"  {t.get('action','?'):4s} {t.get('symbol','?'):6s} "
            f"{t.get('shares',0):8.2f} sh  |  {t.get('rejection_reason','')}"
        )
    return "\n".join(lines)
