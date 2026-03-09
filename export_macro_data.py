"""
export_macro_data.py
Run this script to:
  1. Fetch all FRED macro indicators
  2. Save them to macro_data_export.csv
  3. Generate claude_prompt.txt — the full prompt ready to paste into Claude desktop
"""

import json
import os
import data_utils
from datetime import datetime

OUTPUT_CSV    = "macro_data_export.csv"
OUTPUT_PROMPT = "claude_prompt.txt"
OUTPUT_JSON   = "macro_indicators_raw.json"

ETF_UNIVERSE = {
    "DGHU": "XBI",  "DGHE": "EMQQ", "DGLU": "XLV",  "DGLE": "INDA",
    "DVHU": "SDY",  "DVHE": "EELV", "DVLU": "SPLV",  "DVLE": "EELV",
    "CGHU": "SMH",  "CGHE": "EEM",  "CGLU": "RSP",  "CGLE": "CQQQ",
    "CVHU": "XLE",  "CVHE": "AVES", "CVLU": "XLI",   "CVLE": "FEMS",
}

BUCKET_AXES = {
    "DGHU": "D/G/H/U", "DGHE": "D/G/H/E", "DGLU": "D/G/L/U", "DGLE": "D/G/L/E",
    "DVHU": "D/V/H/U", "DVHE": "D/V/H/E", "DVLU": "D/V/L/U", "DVLE": "D/V/L/E",
    "CGHU": "C/G/H/U", "CGHE": "C/G/H/E", "CGLU": "C/G/L/U", "CGLE": "C/G/L/E",
    "CVHU": "C/V/H/U", "CVHE": "C/V/H/E", "CVLU": "C/V/L/U", "CVLE": "C/V/L/E",
}


def main():
    print("=" * 60)
    print("FETCHING FRED MACRO INDICATORS...")
    print("=" * 60)

    indicators = data_utils.get_macro_indicators()

    if not indicators:
        print("ERROR: No indicators fetched. Check your FRED_API_KEY in .env")
        return

    today = datetime.today().strftime("%Y-%m-%d")

    # ── 1. Save CSV ──────────────────────────────────────────────
    rows = []
    for key, ind in indicators.items():
        rows.append({
            "key":        key,
            "indicator":  ind["label"],
            "value":      ind["value"],
            "unit":       ind["unit"],
            "trend":      ind["trend"],
        })

    import csv
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["key", "indicator", "value", "unit", "trend"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"[OK] Saved indicator table to: {OUTPUT_CSV}")

    # ── 2. Save raw JSON (for re-use) ────────────────────────────
    serializable = {}
    for key, ind in indicators.items():
        serializable[key] = {
            "label": ind["label"],
            "value": ind["value"],
            "unit":  ind["unit"],
            "trend": ind["trend"],
        }
    with open(OUTPUT_JSON, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"[OK] Saved raw JSON to:        {OUTPUT_JSON}")

    # ── 3. Build the prompt for Claude desktop ───────────────────
    indicator_lines = []
    for key, ind in indicators.items():
        arrow = {"rising": "↑", "falling": "↓", "stable": "→"}.get(ind["trend"], "→")
        indicator_lines.append(
            f"  {key:30s}  {ind['label']:45s}  "
            f"{ind['value']:>10.3f} {ind['unit']:10s}  {arrow} {ind['trend'].upper()}"
        )
    indicator_block = "\n".join(indicator_lines)

    bucket_lines = "\n".join(
        f"  {b}: {ETF_UNIVERSE[b]:6s}  (axes: {BUCKET_AXES[b]})"
        for b in ETF_UNIVERSE
    )

    prompt = f"""You are a Chief Investment Officer and macro analyst.
Today's date: {today}

=============================================================
TASK A — MACRO INDICATOR INTERPRETATION
=============================================================
Below are the latest FRED economic indicators (Jan 2023 to {today}).
For each one, provide a ONE-LINE interpretation (max 15 words) explaining
what it signals for markets. Then write a 3-4 sentence MACRO REGIME NARRATIVE.

FRED INDICATORS:
{indicator_block}

=============================================================
TASK B — AXIS SCORING & PORTFOLIO ALLOCATION
=============================================================
Using the full macro picture above, score each of these 4 axes:
  1. Defensive vs Cyclical
  2. Growth vs Value
  3. High Beta vs Low Beta
  4. US vs Emerging Markets

For each axis: state which side is favored, confidence (0.0-1.0),
and 2-3 sentences of reasoning using ALL indicators holistically.

Then allocate across all 16 strategy buckets:
{bucket_lines}

Axes key: D=Defensive, C=Cyclical, G=Growth, V=Value,
          H=High Beta, L=Low Beta, U=US, E=Emerging Markets

HARD CONSTRAINTS:
- All 16 weights must sum to EXACTLY 100.0
- No single bucket > 40%
- No sub-strategy (D, C, G, V, H, L, U, E) total > 70%
- Minimum weight per bucket: 0.5%
- No cash — fully invested

=============================================================
RESPONSE FORMAT — return ONLY this JSON, nothing else:
=============================================================
{{
  "interpretations": {{
    "yield_curve_spread": "one-line interpretation",
    "cpi_yoy": "one-line interpretation",
    "unemployment_gap": "one-line interpretation",
    "output_gap": "one-line interpretation",
    "sp500_eps": "one-line interpretation",
    "fed_funds_rate": "one-line interpretation"
  }},
  "macro_regime_narrative": "3-4 sentence narrative here",
  "axis_scores": {{
    "defensive_cyclical": {{
      "favored": "Defensive or Cyclical",
      "confidence": 0.0,
      "reasoning": "2-3 sentences"
    }},
    "growth_value": {{
      "favored": "Growth or Value",
      "confidence": 0.0,
      "reasoning": "2-3 sentences"
    }},
    "high_low_beta": {{
      "favored": "High Beta or Low Beta",
      "confidence": 0.0,
      "reasoning": "2-3 sentences"
    }},
    "us_em": {{
      "favored": "US or Emerging Markets",
      "confidence": 0.0,
      "reasoning": "2-3 sentences"
    }}
  }},
  "allocation": [
    {{"strategy_bucket": "DGHU", "ticker": "XBI",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DGHE", "ticker": "EMQQ", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DGLU", "ticker": "XLV",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DGLE", "ticker": "INDA", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DVHU", "ticker": "SDY",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DVHE", "ticker": "EELV", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DVLU", "ticker": "SPLV", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "DVLE", "ticker": "EELV", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CGHU", "ticker": "SMH",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CGHE", "ticker": "EEM",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CGLU", "ticker": "RSP", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CGLE", "ticker": "CQQQ", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CVHU", "ticker": "XLE",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CVHE", "ticker": "AVES", "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CVLU", "ticker": "XLI",  "weight_pct": 0.0, "rationale": "one line"}},
    {{"strategy_bucket": "CVLE", "ticker": "FEMS", "weight_pct": 0.0, "rationale": "one line"}}
  ]
}}"""

    with open(OUTPUT_PROMPT, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[OK] Saved Claude prompt to:   {OUTPUT_PROMPT}")

    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print(f"1. Open '{OUTPUT_PROMPT}' and copy ALL of its contents")
    print("2. Paste into Claude desktop (claude.ai) and send")
    print("3. Copy Claude's JSON response")
    print("4. Paste it back to Claude Code here")
    print("   and say: 'here is the claude desktop response'")
    print("=" * 60)


if __name__ == "__main__":
    main()
