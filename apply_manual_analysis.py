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
    "yield_curve_spread": "Curve re-steepening signals easing cycle underway, reducing recession risk.",
    "cpi_yoy": "Inflation re-accelerating above target, limiting Fed's room to cut further.",
    "unemployment_gap": "Labor market near full employment, economy running slightly hot.",
    "output_gap": "Economy significantly above potential, suggesting overheating pressures building.",
    "sp500_eps": "Earnings momentum weakening, corporate profitability under pressure.",
    "fed_funds_rate": "Fed in easing cycle but cutting cautiously given sticky inflation."
  },
  "macro_regime_narrative": "The US economy is operating in a late-cycle expansion characterized by above-potential output, near-full employment, and re-accelerating inflation — a challenging combination for risk assets. The Fed is cutting rates but faces a difficult balancing act as CPI trends higher while EPS growth deteriorates, squeezing corporate margins. The re-steepening yield curve confirms the easing bias but also reflects inflation risk premium being priced back in. This environment favors quality and defensiveness over pure cyclical risk, with selective exposure to value where earnings resilience is strongest.",
  "axis_scores": {
    "defensive_cyclical": {
      "favored": "Defensive",
      "confidence": 0.65,
      "reasoning": "Falling EPS combined with an overheating economy and rising CPI creates a margin compression environment unfavorable to cyclicals. The output gap at 32% above potential historically precedes slowdowns, and with the unemployment gap near zero there is little room for further labor-driven demand acceleration. Defensive sectors with pricing power and stable cash flows are better positioned."
    },
    "growth_value": {
      "favored": "Value",
      "confidence": 0.60,
      "reasoning": "Declining EPS momentum and sticky inflation make high-multiple growth stocks vulnerable to re-rating as discount rates remain elevated. Value stocks with lower duration and stronger near-term cash flows offer better protection in a margin compression environment. The Fed cutting slowly means rates stay relatively high, which continues to pressure long-duration growth valuations."
    },
    "high_low_beta": {
      "favored": "Low Beta",
      "confidence": 0.70,
      "reasoning": "With the economy above potential and earnings deteriorating, volatility risk is asymmetrically skewed to the downside. High beta names are most exposed to any growth disappointment or inflation surprise that forces the Fed to pause cuts. Low beta provides downside cushion while still participating in any continued equity upside."
    },
    "us_em": {
      "favored": "US",
      "confidence": 0.60,
      "reasoning": "The Fed easing cycle is a modest positive for EM but rising US inflation and a still-elevated dollar create headwinds for emerging market assets. Falling global EPS and the overheating US economy suggest risk-off pressure that typically hits EM harder than US. A modest EM allocation is warranted given the steepening curve but US quality should dominate."
    }
  },
  "allocation": [
    {"strategy_bucket": "DGHU", "ticker": "XBI",  "weight_pct": 3.5,  "rationale": "Defensive biotech offers growth optionality but high beta limits sizing given risk-off bias."},
    {"strategy_bucket": "DGHE", "ticker": "EMQQ", "weight_pct": 2.0,  "rationale": "EM tech growth exposure kept minimal given dollar strength and EM headwinds."},
    {"strategy_bucket": "DGLU", "ticker": "XLV",  "weight_pct": 12.0, "rationale": "Healthcare is core defensive growth holding with stable earnings and pricing power."},
    {"strategy_bucket": "DGLE", "ticker": "INDA", "weight_pct": 3.0,  "rationale": "India structural growth story intact but sized conservatively given EM caution."},
    {"strategy_bucket": "DVHU", "ticker": "SDY",  "weight_pct": 6.0,  "rationale": "Dividend aristocrats offer value and income with moderate beta in late cycle."},
    {"strategy_bucket": "DVHE", "ticker": "EELV", "weight_pct": 2.5,  "rationale": "EM low-vol value provides diversification but kept small given EM headwinds."},
    {"strategy_bucket": "DVLU", "ticker": "SPLV", "weight_pct": 13.0, "rationale": "Low volatility US value is the highest conviction position given macro regime."},
    {"strategy_bucket": "DVLE", "ticker": "EELV", "weight_pct": 2.0,  "rationale": "Defensive EM value allocation kept minimal, complements DVHE exposure."},
    {"strategy_bucket": "CGHU", "ticker": "SMH",  "weight_pct": 7.0,  "rationale": "Semiconductors retain structural tailwind from AI but sized for high beta risk."},
    {"strategy_bucket": "CGHE", "ticker": "EEM",  "weight_pct": 3.5,  "rationale": "Broad EM cyclical growth included for diversification at modest weight."},
    {"strategy_bucket": "CGLU", "ticker": "QQQM", "weight_pct": 10.0, "rationale": "Large cap US tech growth offers quality cyclical exposure with lower beta profile."},
    {"strategy_bucket": "CGLE", "ticker": "CQQQ", "weight_pct": 2.5,  "rationale": "China tech allocation minimal given regulatory and macro uncertainty."},
    {"strategy_bucket": "CVHU", "ticker": "XLE",  "weight_pct": 6.5,  "rationale": "Energy value benefits from sticky inflation keeping commodity prices elevated."},
    {"strategy_bucket": "CVHE", "ticker": "AVES", "weight_pct": 3.0,  "rationale": "EM value exposure via AVES provides commodity and EM value diversification."},
    {"strategy_bucket": "CVLU", "ticker": "XLI",  "weight_pct": 11.0, "rationale": "Industrials offer cyclical value with lower beta, benefits from infrastructure spend."},
    {"strategy_bucket": "CVLE", "ticker": "FEMS", "weight_pct": 12.5, "rationale": "EM small cap value rounds out portfolio with attractive valuations vs US peers."}
  ]
}

SIM_START_DATE = "2026-01-02"


def main():
    print("=" * 60)
    print("APPLYING MANUAL MACRO ANALYSIS")
    print("=" * 60)

    # Ensure DB is ready
    db.initialize_db()
    today = datetime.today().strftime("%Y-%m-%d")

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
