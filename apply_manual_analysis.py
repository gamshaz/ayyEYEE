"""
apply_manual_analysis.py
Feeds the Claude desktop macro analysis JSON into the database,
fetches live prices, and initializes all 16 portfolio positions.
Run once after export_macro_data.py + Claude desktop analysis.
"""

import json
from datetime import datetime
import database as db
import data_utils
import execution_agent

# ── Paste the full JSON from Claude desktop here ──────────────────────────────
CLAUDE_RESPONSE = {
  "interpretations": {
    "yield_curve_spread": "Steepening curve signals easing cycle reducing near-term recession risk.",
    "cpi_yoy": "Inflation re-accelerating above target constrains Fed's ability to cut aggressively.",
    "unemployment_gap": "Labor market at full employment with economy running marginally hot.",
    "output_gap": "Economy well above potential output, overheating pressures likely building.",
    "sp500_eps": "Deteriorating earnings momentum signals corporate margin compression ahead.",
    "fed_funds_rate": "Fed cutting cautiously, balancing growth support against sticky inflation."
  },
  "macro_regime_narrative": "The macro regime remains late-cycle expansion with simultaneous overheating and earnings deterioration — a classically difficult environment for risk assets. The Fed is easing but constrained by re-accelerating CPI, meaning real rates remain relatively elevated and long-duration assets face continued pressure. Falling EPS against an above-potential economy suggests margins are being squeezed rather than demand collapsing, which favors quality and defensiveness over pure cyclical beta. The steepening yield curve is a modest positive for financial conditions but insufficient to overcome the fundamental headwinds facing high-beta and growth-heavy portfolios.",
  "axis_scores": {
    "defensive_cyclical": {
      "favored": "Defensive",
      "confidence": 0.65,
      "reasoning": "Falling EPS with an overheating economy points to margin compression rather than demand-led growth, which historically hurts cyclicals more than defensives. The output gap at elevated levels combined with rising CPI suggests the economy is closer to a peak than a trough. Defensive sectors with pricing power and predictable cash flows offer better risk-adjusted returns in this environment."
    },
    "growth_value": {
      "favored": "Value",
      "confidence": 0.60,
      "reasoning": "Declining EPS momentum makes it difficult to justify elevated growth multiples, particularly with the Fed cutting slowly and real rates staying positive. Value stocks with lower duration and stronger near-term earnings visibility are better positioned to weather margin compression. Rising CPI also benefits value sectors like energy and industrials with real asset exposure."
    },
    "high_low_beta": {
      "favored": "Low Beta",
      "confidence": 0.70,
      "reasoning": "The combination of above-potential output, rising inflation and falling earnings creates asymmetric downside risk that high beta names are most exposed to. Any growth disappointment or inflation surprise forcing a Fed pause would disproportionately hurt high beta positions. Low beta provides capital preservation while still participating in any continued equity upside from the easing cycle."
    },
    "us_em": {
      "favored": "US",
      "confidence": 0.58,
      "reasoning": "The Fed easing cycle provides modest EM tailwind but elevated US inflation supports a stronger dollar which historically headwinds EM assets. Falling global EPS and geopolitical uncertainty favor US quality over EM cyclical exposure. A selective EM allocation in value and low-vol buckets is warranted but US should remain the portfolio anchor."
    }
  },
  "allocation": [
    {"strategy_bucket": "DGHU", "ticker": "XBI",  "weight_pct": 3.5,  "rationale": "Biotech defensive growth keeps optionality but high beta limits sizing in risk-off regime."},
    {"strategy_bucket": "DGHE", "ticker": "EMQQ", "weight_pct": 2.0,  "rationale": "EM tech growth kept minimal given dollar headwinds and weak EM earnings momentum."},
    {"strategy_bucket": "DGLU", "ticker": "XLV",  "weight_pct": 12.0, "rationale": "Healthcare is highest conviction defensive growth with stable earnings and pricing power."},
    {"strategy_bucket": "DGLE", "ticker": "INDA", "weight_pct": 3.0,  "rationale": "India structural growth story intact, sized conservatively given broad EM caution."},
    {"strategy_bucket": "DVHU", "ticker": "SDY",  "weight_pct": 6.0,  "rationale": "Dividend aristocrats provide income and value with moderate beta in late cycle."},
    {"strategy_bucket": "DVHE", "ticker": "EELV", "weight_pct": 2.5,  "rationale": "EM low-vol defensive value adds diversification, kept small given EM headwinds."},
    {"strategy_bucket": "DVLU", "ticker": "SPLV", "weight_pct": 13.0, "rationale": "Highest conviction position — low vol US value perfectly matches macro regime."},
    {"strategy_bucket": "DVLE", "ticker": "EELV", "weight_pct": 2.0,  "rationale": "Defensive EM low-vol rounds out EM defensive allocation alongside DVHE."},
    {"strategy_bucket": "CGHU", "ticker": "SMH",  "weight_pct": 7.0,  "rationale": "Semiconductors retain AI structural tailwind, sized for elevated but manageable beta risk."},
    {"strategy_bucket": "CGHE", "ticker": "EEM",  "weight_pct": 3.5,  "rationale": "Broad EM cyclical growth included for diversification at modest weight only."},
    {"strategy_bucket": "CGLU", "ticker": "QQQM", "weight_pct": 10.0, "rationale": "Large cap US tech offers quality cyclical growth with relatively lower beta profile."},
    {"strategy_bucket": "CGLE", "ticker": "CQQQ", "weight_pct": 2.5,  "rationale": "China tech kept minimal given regulatory overhang and macro uncertainty."},
    {"strategy_bucket": "CVHU", "ticker": "XLE",  "weight_pct": 6.5,  "rationale": "Energy benefits from sticky inflation keeping commodity prices supported."},
    {"strategy_bucket": "CVHE", "ticker": "AVES", "weight_pct": 3.0,  "rationale": "EM value via AVES provides commodity exposure and EM value diversification."},
    {"strategy_bucket": "CVLU", "ticker": "XLI",  "weight_pct": 11.0, "rationale": "Industrials offer cyclical value with lower beta, supported by infrastructure spending."},
    {"strategy_bucket": "CVLE", "ticker": "FEMS", "weight_pct": 12.5, "rationale": "EM small cap value offers attractive valuations vs US peers, rounds out portfolio."}
  ]
}

FRESH_START_DATE = "2026-01-02"   # used only when DB has no existing simulation


def main():
    print("=" * 60)
    print("APPLYING MANUAL MACRO ANALYSIS")
    print("=" * 60)

    # Always reset DB and start fresh at FRESH_START_DATE
    print("    Resetting database...")
    db.reset_db()
    today = datetime.today().strftime("%Y-%m-%d")
    SIM_START_DATE = FRESH_START_DATE
    print(f"    Sim date: {SIM_START_DATE}")

    # ── 1. Save macro interpretations to macro_log ────────────────
    print("\n[1/4] Saving macro indicator log...")
    # Load raw indicator values from the saved JSON (for value/trend fields)
    raw_indicators = {}
    try:
        import os
        if os.path.exists("macro_indicators_raw.json"):
            with open("macro_indicators_raw.json") as f:
                raw_indicators = json.load(f)
    except Exception:
        pass

    interpretations = CLAUDE_RESPONSE.get("interpretations", {})
    for key, interp in interpretations.items():
        ind = raw_indicators.get(key, {})
        db.insert_macro_log(
            date           = today,
            indicator      = ind.get("label", key),
            value          = ind.get("value", 0.0),
            trend          = ind.get("trend", "stable"),
            interpretation = interp,
        )
    print(f"    Saved {len(interpretations)} indicator entries.")

    # ── 2. Save target allocation ─────────────────────────────────
    print("[2/4] Saving strategic allocation...")
    allocation = CLAUDE_RESPONSE.get("allocation", [])
    db.save_target_allocation(allocation)
    total_weight = sum(r["weight_pct"] for r in allocation)
    print(f"    Saved {len(allocation)} buckets  |  Total weight: {total_weight:.2f}%")

    # ── 3. Fetch live prices ──────────────────────────────────────
    print(f"[3/4] Fetching live prices for {SIM_START_DATE}...")
    prices = data_utils.get_all_current_prices(SIM_START_DATE)
    fetched = [t for t, p in prices.items() if p]
    missing = [r["ticker"] for r in allocation if r["ticker"] not in prices or not prices[r["ticker"]]]
    print(f"    Fetched: {len(fetched)} tickers")
    if missing:
        print(f"    WARNING — no price for: {missing}")

    # ── 4. Initialize positions ───────────────────────────────────
    print("[4/4] Initializing portfolio positions...")
    remaining_cash = execution_agent.initialize_positions_from_allocation(
        allocation, prices, db.INITIAL_CASH, SIM_START_DATE
    )
    print(f"    Remaining cash: ${remaining_cash:,.2f}")

    # ── Summary ───────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("PORTFOLIO INITIALIZED SUCCESSFULLY")
    print("=" * 60)
    positions = db.get_positions()
    print(f"\n{'BUCKET':<8} {'TICKER':<6} {'SHARES':>10} {'PRICE':>10} {'MKT VALUE':>14} {'WEIGHT':>8}")
    print("-" * 60)
    total_mv = 0
    for pos in sorted(positions, key=lambda x: x["market_value"], reverse=True):
        mv = pos["market_value"]
        total_mv += mv
        wt = mv / db.INITIAL_CASH * 100
        print(f"{pos['strategy_bucket']:<8} {pos['symbol']:<6} {pos['shares']:>10.3f} "
              f"${pos['current_price']:>9.2f} ${mv:>13,.2f} {wt:>7.2f}%")
    print("-" * 60)
    print(f"{'TOTAL':>26} ${total_mv:>13,.2f} {total_mv/db.INITIAL_CASH*100:>7.2f}%")
    print(f"{'CASH':>26} ${remaining_cash:>13,.2f}")
    print(f"{'TOTAL EQUITY':>26} ${total_mv + remaining_cash:>13,.2f}")
    print()
    print("Now refresh the Streamlit app — your portfolio is live in Tab 2.")


if __name__ == "__main__":
    main()
