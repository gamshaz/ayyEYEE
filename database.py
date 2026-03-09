import sqlite3
import csv
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finance_game.db")
CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transactions.csv")

# ETF universe mapping: strategy bucket -> ticker
ETF_UNIVERSE = {
    "DGHU": "XBI",   # Defensive, Growth, High Beta, US
    "DGHE": "EMQQ",  # Defensive, Growth, High Beta, EM
    "DGLU": "XLV",   # Defensive, Growth, Low Beta, US
    "DGLE": "INDA",  # Defensive, Growth, Low Beta, EM
    "DVHU": "SDY",   # Defensive, Value, High Beta, US
    "DVHE": "EELV",  # Defensive, Value, High Beta, EM
    "DVLU": "SPLV",  # Defensive, Value, Low Beta, US
    "DVLE": "EELV",  # Defensive, Value, Low Beta, EM
    "CGHU": "SMH",   # Cyclical, Growth, High Beta, US
    "CGHE": "EEM",   # Cyclical, Growth, High Beta, EM
    "CGLU": "RSP",   # Cyclical, Growth, Low Beta, US
    "CGLE": "CQQQ",  # Cyclical, Growth, Low Beta, EM
    "CVHU": "XLE",   # Cyclical, Value, High Beta, US
    "CVHE": "AVES",  # Cyclical, Value, High Beta, EM
    "CVLU": "XLI",   # Cyclical, Value, Low Beta, US
    "CVLE": "FEMS",  # Cyclical, Value, Low Beta, EM
}

INITIAL_CASH = 1_000_000.0


def get_connection():
    # Returns a new SQLite connection to the database
    return sqlite3.connect(DB_PATH)


def initialize_db():
    # Creates all tables if they don't exist; called at app startup
    conn = get_connection()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS simulation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            current_date TEXT NOT NULL,
            cash_balance REAL NOT NULL,
            total_portfolio_value REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT NOT NULL,
            strategy_bucket TEXT NOT NULL,
            shares REAL NOT NULL DEFAULT 0,
            average_cost REAL NOT NULL DEFAULT 0,
            current_price REAL NOT NULL DEFAULT 0,
            market_value REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (symbol, strategy_bucket)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            action TEXT NOT NULL,
            symbol TEXT NOT NULL,
            shares REAL NOT NULL,
            price REAL NOT NULL,
            reason TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS daily_snapshots (
            date TEXT PRIMARY KEY,
            cash REAL NOT NULL,
            holdings_value REAL NOT NULL,
            total_equity REAL NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS macro_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            indicator TEXT NOT NULL,
            value REAL,
            trend TEXT,
            interpretation TEXT
        )
    """)

    # Target allocation table: stores macro agent output
    c.execute("""
        CREATE TABLE IF NOT EXISTS target_allocation (
            strategy_bucket TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            weight_pct REAL NOT NULL,
            rationale TEXT
        )
    """)

    conn.commit()
    conn.close()


def reset_db():
    # Drops and recreates the database file for a fresh simulation
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    initialize_db()


def get_simulation_state():
    # Retrieves the latest simulation row (date + balances)
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT "current_date", cash_balance, total_portfolio_value FROM simulation ORDER BY id DESC LIMIT 1')
    row = c.fetchone()
    conn.close()
    if row:
        return {"current_date": row[0], "cash_balance": row[1], "total_portfolio_value": row[2]}
    return None


def set_simulation_state(current_date: str, cash_balance: float, total_portfolio_value: float):
    # Inserts a new simulation state row
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO simulation (current_date, cash_balance, total_portfolio_value) VALUES (?, ?, ?)",
        (current_date, cash_balance, total_portfolio_value)
    )
    conn.commit()
    conn.close()


def get_positions():
    # Returns all open positions as a list of dicts
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT symbol, strategy_bucket, shares, average_cost, current_price, market_value FROM positions")
    rows = c.fetchall()
    conn.close()
    return [
        {
            "symbol": r[0], "strategy_bucket": r[1], "shares": r[2],
            "average_cost": r[3], "current_price": r[4], "market_value": r[5]
        }
        for r in rows
    ]


def upsert_position(symbol: str, strategy_bucket: str, shares: float,
                    average_cost: float, current_price: float, market_value: float):
    # Inserts or updates a single position row
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO positions (symbol, strategy_bucket, shares, average_cost, current_price, market_value)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(symbol, strategy_bucket) DO UPDATE SET
            shares=excluded.shares,
            average_cost=excluded.average_cost,
            current_price=excluded.current_price,
            market_value=excluded.market_value
    """, (symbol, strategy_bucket, shares, average_cost, current_price, market_value))
    conn.commit()
    conn.close()


def delete_position(symbol: str, strategy_bucket: str):
    # Removes a position row when shares reach zero
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM positions WHERE symbol=? AND strategy_bucket=?", (symbol, strategy_bucket))
    conn.commit()
    conn.close()


def insert_transaction(date: str, action: str, symbol: str,
                       shares: float, price: float, reason: str):
    # Logs a trade to the transactions table
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (date, action, symbol, shares, price, reason) VALUES (?, ?, ?, ?, ?, ?)",
        (date, action, symbol, shares, price, reason)
    )
    conn.commit()
    conn.close()

    # Append to CSV for Excel export
    value = shares * price
    write_header = not os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(["Date", "Action", "Symbol", "Shares", "Price", "Value", "Reason"])
        writer.writerow([date, action, symbol, f"{shares:.4f}", f"{price:.4f}", f"{value:.2f}", reason])


def get_transactions():
    # Returns all transactions ordered by date descending
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT id, date, action, symbol, shares, price, reason FROM transactions ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "date": r[1], "action": r[2], "symbol": r[3],
         "shares": r[4], "price": r[5], "reason": r[6]}
        for r in rows
    ]


def insert_daily_snapshot(date: str, cash: float, holdings_value: float, total_equity: float):
    # Saves end-of-day portfolio snapshot (upsert by date)
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO daily_snapshots (date, cash, holdings_value, total_equity)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            cash=excluded.cash,
            holdings_value=excluded.holdings_value,
            total_equity=excluded.total_equity
    """, (date, cash, holdings_value, total_equity))
    conn.commit()
    conn.close()


def get_daily_snapshots():
    # Returns all daily snapshots sorted by date ascending
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT date, cash, holdings_value, total_equity FROM daily_snapshots ORDER BY date ASC")
    rows = c.fetchall()
    conn.close()
    return [{"date": r[0], "cash": r[1], "holdings_value": r[2], "total_equity": r[3]} for r in rows]


def insert_macro_log(date: str, indicator: str, value: float, trend: str, interpretation: str):
    # Logs a macro indicator reading to macro_log
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO macro_log (date, indicator, value, trend, interpretation) VALUES (?, ?, ?, ?, ?)",
        (date, indicator, value, trend, interpretation)
    )
    conn.commit()
    conn.close()


def get_macro_log():
    # Returns the most recent macro log entries per indicator
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT indicator, value, trend, interpretation, date
        FROM macro_log
        WHERE id IN (
            SELECT MAX(id) FROM macro_log GROUP BY indicator
        )
        ORDER BY indicator
    """)
    rows = c.fetchall()
    conn.close()
    return [{"indicator": r[0], "value": r[1], "trend": r[2], "interpretation": r[3], "date": r[4]} for r in rows]


def save_target_allocation(allocation: list):
    # Saves the macro agent's strategic allocation (replaces previous)
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM target_allocation")
    for row in allocation:
        c.execute(
            "INSERT INTO target_allocation (strategy_bucket, ticker, weight_pct, rationale) VALUES (?, ?, ?, ?)",
            (row["strategy_bucket"], row["ticker"], row["weight_pct"], row.get("rationale", ""))
        )
    conn.commit()
    conn.close()


def get_target_allocation():
    # Returns the stored strategic allocation as list of dicts
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT strategy_bucket, ticker, weight_pct, rationale FROM target_allocation ORDER BY weight_pct DESC")
    rows = c.fetchall()
    conn.close()
    return [{"strategy_bucket": r[0], "ticker": r[1], "weight_pct": r[2], "rationale": r[3]} for r in rows]
