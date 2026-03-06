"""
execution_agent.py - Trade Execution Agent

Executes approved trades against the SQLite database.
Updates cash, share counts, transaction log, and daily snapshots.
No market impact model — trades execute at the price provided.
"""

from typing import List, Dict, Any
import database as db


def execute_trades(
    approved_trades: List[Dict[str, Any]],
    current_date: str,
    prices: Dict[str, float],
    cash: float,
    positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Executes all approved trades and persists results to the database.

    Args:
        approved_trades: Trades approved by risk_agent.validate_trades()
        current_date:    ISO date string (YYYY-MM-DD)
        prices:          Dict of {ticker: execution_price}
        cash:            Current cash balance before execution
        positions:       Current positions list from DB

    Returns:
        Dict with keys:
          'new_cash':         updated cash balance
          'executed_trades':  list of trades that actually executed
          'execution_log':    human-readable string of what happened
    """
    executed = []
    log_lines = [f"EXECUTION LOG — {current_date}", "═" * 50]

    # Build a mutable positions lookup for in-memory updates
    pos_map = _build_position_map(positions)

    for trade in approved_trades:
        symbol  = trade["symbol"]
        action  = trade["action"].upper()
        shares  = float(trade["shares"])
        price   = prices.get(symbol, 0.0)
        reason  = trade.get("reason", "")

        if price <= 0 or shares <= 0:
            log_lines.append(f"  SKIP  {symbol}: invalid price or shares")
            continue

        trade_value = shares * price

        if action == "BUY":
            cash = _execute_buy(symbol, shares, price, trade_value, cash, pos_map, reason)
            log_lines.append(
                f"  BUY   {symbol:6s}  {shares:10.4f} sh @ ${price:10.4f}  = ${trade_value:>12,.2f}  | {reason}"
            )

        elif action == "SELL":
            cash = _execute_sell(symbol, shares, price, trade_value, cash, pos_map, reason)
            log_lines.append(
                f"  SELL  {symbol:6s}  {shares:10.4f} sh @ ${price:10.4f}  = ${trade_value:>12,.2f}  | {reason}"
            )

        # Log to transactions table
        db.insert_transaction(current_date, action, symbol, shares, price, reason)
        executed.append(trade)

    # Persist updated positions to DB
    _flush_positions(pos_map, prices)

    # Update simulation state with new cash
    holdings_value = _compute_holdings_value(pos_map, prices)
    total_equity   = cash + holdings_value
    db.set_simulation_state(current_date, cash, total_equity)

    log_lines.append("─" * 50)
    log_lines.append(f"  Cash after execution:  ${cash:>14,.2f}")
    log_lines.append(f"  Holdings value:        ${holdings_value:>14,.2f}")
    log_lines.append(f"  Total equity:          ${total_equity:>14,.2f}")

    return {
        "new_cash":        cash,
        "executed_trades": executed,
        "execution_log":   "\n".join(log_lines),
    }


def save_daily_snapshot(current_date: str, cash: float, positions: list, prices: dict):
    """
    Saves an end-of-day portfolio snapshot to daily_snapshots table.
    Should be called at the end of each trading day even if no trades occur.
    """
    holdings_value = sum(
        pos["shares"] * prices.get(pos["symbol"], pos.get("current_price", 0))
        for pos in positions
    )
    total_equity = cash + holdings_value
    db.insert_daily_snapshot(current_date, cash, holdings_value, total_equity)
    return total_equity


def initialize_positions_from_allocation(
    allocation: list,
    prices: dict,
    cash: float,
    current_date: str,
) -> float:
    """
    Buys into all strategy buckets according to the macro agent's allocation.
    Called once at simulation initialization after user confirms macro analysis.

    allocation: list of {strategy_bucket, ticker, weight_pct, rationale}
    prices:     current prices dict {ticker: price}
    cash:       initial cash ($1,000,000)

    Returns remaining cash after initial purchases.
    """
    log_lines = [f"INITIAL ALLOCATION — {current_date}", "═" * 60]
    pos_map = {}

    for row in allocation:
        bucket     = row["strategy_bucket"]
        ticker     = row["ticker"]
        weight_pct = row["weight_pct"]
        rationale  = row.get("rationale", "Macro allocation")
        price      = prices.get(ticker, 0.0)

        if price <= 0:
            log_lines.append(f"  SKIP  {ticker}: no price available")
            continue

        target_value = (weight_pct / 100.0) * cash
        shares       = target_value / price
        trade_value  = shares * price

        # Record in pos_map
        if ticker not in pos_map:
            pos_map[ticker] = {"strategy_bucket": bucket, "shares": 0.0, "average_cost": price}
        pos_map[ticker]["shares"] += shares

        # Log transaction
        db.insert_transaction(current_date, "BUY", ticker, shares, price, f"Initial allocation: {bucket} ({weight_pct:.1f}%)")
        log_lines.append(
            f"  BUY   {ticker:6s}  {shares:10.4f} sh @ ${price:8.4f}  "
            f"= ${trade_value:>12,.2f}  [{bucket} {weight_pct:.1f}%]"
        )

    # Deduct all spend from cash
    total_spent = sum(
        pos_map[tk]["shares"] * prices.get(tk, 0)
        for tk in pos_map
    )
    remaining_cash = cash - total_spent

    # Flush to DB
    _flush_positions(pos_map, prices)

    holdings_value = total_spent
    total_equity   = remaining_cash + holdings_value
    db.set_simulation_state(current_date, remaining_cash, total_equity)
    db.insert_daily_snapshot(current_date, remaining_cash, holdings_value, total_equity)

    log_lines.append("─" * 60)
    log_lines.append(f"  Total invested:        ${total_spent:>14,.2f}")
    log_lines.append(f"  Remaining cash:        ${remaining_cash:>14,.2f}")
    print("\n".join(log_lines))

    return remaining_cash


# ─── Private helpers ───────────────────────────────────────────────────────────

def _build_position_map(positions: list) -> dict:
    # Converts the positions list into a mutable dict keyed by ticker
    pos_map = {}
    for p in positions:
        ticker = p["symbol"]
        pos_map[ticker] = {
            "strategy_bucket": p["strategy_bucket"],
            "shares":          p["shares"],
            "average_cost":    p["average_cost"],
        }
    return pos_map


def _execute_buy(symbol, shares, price, trade_value, cash, pos_map, reason) -> float:
    # Updates in-memory pos_map for a BUY trade; returns updated cash
    if symbol in pos_map:
        old_shares = pos_map[symbol]["shares"]
        old_cost   = pos_map[symbol]["average_cost"]
        new_shares = old_shares + shares
        # Weighted average cost basis
        new_avg_cost = ((old_shares * old_cost) + (shares * price)) / new_shares
        pos_map[symbol]["shares"]       = new_shares
        pos_map[symbol]["average_cost"] = new_avg_cost
    else:
        pos_map[symbol] = {
            "strategy_bucket": "UNCLASSIFIED",
            "shares":          shares,
            "average_cost":    price,
        }
    return cash - trade_value


def _execute_sell(symbol, shares, price, trade_value, cash, pos_map, reason) -> float:
    # Updates in-memory pos_map for a SELL trade; returns updated cash
    if symbol in pos_map:
        pos_map[symbol]["shares"] -= shares
        if pos_map[symbol]["shares"] <= 0.0001:
            del pos_map[symbol]
    return cash + trade_value


def _flush_positions(pos_map: dict, prices: dict):
    # Writes all in-memory positions back to the database
    # First delete all then re-insert to avoid stale rows
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM positions")
    for ticker, pos in pos_map.items():
        price = prices.get(ticker, pos.get("average_cost", 0))
        market_value = pos["shares"] * price
        c.execute("""
            INSERT INTO positions (symbol, strategy_bucket, shares, average_cost, current_price, market_value)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            ticker,
            pos.get("strategy_bucket", "UNCLASSIFIED"),
            pos["shares"],
            pos["average_cost"],
            price,
            market_value,
        ))
    conn.commit()
    conn.close()


def _compute_holdings_value(pos_map: dict, prices: dict) -> float:
    # Sums market value of all holdings from in-memory pos_map
    return sum(
        pos["shares"] * prices.get(ticker, 0)
        for ticker, pos in pos_map.items()
    )


def refresh_position_prices(prices: dict):
    """
    Updates current_price and market_value for all positions
    without changing shares or cost basis.
    Called when prices are refreshed without any trades.
    """
    positions = db.get_positions()
    pos_map = _build_position_map(positions)
    _flush_positions(pos_map, prices)
