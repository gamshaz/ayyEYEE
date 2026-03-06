"""
macro_agent.py - Strategic Asset Allocation Agent (runs ONCE at initialization)

Uses the Anthropic Claude API to:
  Phase 1: Fetch FRED macro indicators, compute trends, generate summary + interpretation
  Phase 2: Score each axis (D/C, G/V, H/L, U/E) and produce final allocation
           with user CONFIRM gate between phases.

All FRED data is fetched for Jan 2023 → latest available.
"""

import json
import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv

import data_utils
import database as db

load_dotenv()

MODEL = "claude-sonnet-4-6"

# Axis labels for scoring
AXES = {
    "defensive_cyclical": ("Defensive", "Cyclical"),
    "growth_value":       ("Growth", "Value"),
    "high_low_beta":      ("High Beta", "Low Beta"),
    "us_em":              ("US", "Emerging Markets"),
}

# Full ETF universe with axis breakdown
ETF_UNIVERSE = db.ETF_UNIVERSE

# Strategy bucket axis membership
BUCKET_AXES = {
    "DGHU": {"dc": "D", "gv": "G", "hl": "H", "ue": "U"},
    "DGHE": {"dc": "D", "gv": "G", "hl": "H", "ue": "E"},
    "DGLU": {"dc": "D", "gv": "G", "hl": "L", "ue": "U"},
    "DGLE": {"dc": "D", "gv": "G", "hl": "L", "ue": "E"},
    "DVHU": {"dc": "D", "gv": "V", "hl": "H", "ue": "U"},
    "DVHE": {"dc": "D", "gv": "V", "hl": "H", "ue": "E"},
    "DVLU": {"dc": "D", "gv": "V", "hl": "L", "ue": "U"},
    "DVLE": {"dc": "D", "gv": "V", "hl": "L", "ue": "E"},
    "CGHU": {"dc": "C", "gv": "G", "hl": "H", "ue": "U"},
    "CGHE": {"dc": "C", "gv": "G", "hl": "H", "ue": "E"},
    "CGLU": {"dc": "C", "gv": "G", "hl": "L", "ue": "U"},
    "CGLE": {"dc": "C", "gv": "G", "hl": "L", "ue": "E"},
    "CVHU": {"dc": "C", "gv": "V", "hl": "H", "ue": "U"},
    "CVHE": {"dc": "C", "gv": "V", "hl": "H", "ue": "E"},
    "CVLU": {"dc": "C", "gv": "V", "hl": "L", "ue": "U"},
    "CVLE": {"dc": "C", "gv": "V", "hl": "L", "ue": "E"},
}

# Sub-strategy cap: no single sub-strategy (D, C, G, V, H, L, U, E) > 70%
SUB_STRATEGY_AXES = {
    "D": [b for b, a in BUCKET_AXES.items() if a["dc"] == "D"],
    "C": [b for b, a in BUCKET_AXES.items() if a["dc"] == "C"],
    "G": [b for b, a in BUCKET_AXES.items() if a["gv"] == "G"],
    "V": [b for b, a in BUCKET_AXES.items() if a["gv"] == "V"],
    "H": [b for b, a in BUCKET_AXES.items() if a["hl"] == "H"],
    "L": [b for b, a in BUCKET_AXES.items() if a["hl"] == "L"],
    "U": [b for b, a in BUCKET_AXES.items() if a["ue"] == "U"],
    "E": [b for b, a in BUCKET_AXES.items() if a["ue"] == "E"],
}


def _get_client() -> anthropic.Anthropic:
    # Returns an authenticated Anthropic API client
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not found in environment. Add it to your .env file.")
    return anthropic.Anthropic(api_key=api_key)


def _format_indicators_for_prompt(indicators: dict) -> str:
    # Converts the indicators dict into a structured string for the Claude prompt
    lines = []
    for key, ind in indicators.items():
        trend_arrow = {"rising": "↑", "falling": "↓", "stable": "→"}.get(ind["trend"], "→")
        lines.append(
            f"  {ind['label']:45s}  {ind['value']:>10.3f} {ind['unit']:10s}  {trend_arrow} {ind['trend'].upper()}"
        )
    return "\n".join(lines)


def phase1_analyze(indicators: dict) -> dict:
    """
    Phase 1: Sends macro indicator data to Claude and gets back:
      - One-line interpretation for each indicator
      - Overall macro regime narrative
      - 6-month trend description per indicator

    Returns a dict:
      {
        "summary_rows": [{"indicator", "value", "unit", "trend", "interpretation"}],
        "regime_narrative": str,
        "raw_indicators": indicators
      }
    """
    client = _get_client()
    indicators_text = _format_indicators_for_prompt(indicators)
    today = datetime.today().strftime("%Y-%m-%d")

    prompt = f"""You are a senior macro analyst reviewing current economic conditions as of {today}.

Here are the latest FRED macro indicators (Jan 2023 to present):

{indicators_text}

Your task:
1. For each indicator, provide a ONE-LINE interpretation (max 15 words) explaining what it signals for markets.
2. Write a 3-4 sentence MACRO REGIME NARRATIVE summarizing the overall economic picture.

Respond in JSON with this exact structure:
{{
  "interpretations": {{
    "<indicator_key>": "<one-line interpretation>"
  }},
  "macro_regime_narrative": "<3-4 sentence narrative>"
}}

Keys in interpretations must match exactly: {list(indicators.keys())}

Be concise and precise. Focus on investment implications."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    result = json.loads(raw_text)
    interpretations = result.get("interpretations", {})
    narrative = result.get("macro_regime_narrative", "")

    summary_rows = []
    for key, ind in indicators.items():
        summary_rows.append({
            "indicator":      ind["label"],
            "key":            key,
            "value":          ind["value"],
            "unit":           ind["unit"],
            "trend":          ind["trend"],
            "interpretation": interpretations.get(key, "—"),
        })

    # Persist to macro_log DB table
    today_str = datetime.today().strftime("%Y-%m-%d")
    for row in summary_rows:
        db.insert_macro_log(today_str, row["indicator"], row["value"], row["trend"], row["interpretation"])

    return {
        "summary_rows":      summary_rows,
        "regime_narrative":  narrative,
        "raw_indicators":    indicators,
    }


def phase2_allocate(indicators: dict, feedback: str = "") -> dict:
    """
    Phase 2: Scores the four allocation axes and produces final bucket weights.
    Called after user reviews Phase 1 output and types CONFIRM (or provides feedback).

    Returns:
      {
        "axis_scores":   {axis: {"favored": str, "score": float, "reasoning": str}},
        "allocation":    [{"strategy_bucket", "ticker", "weight_pct", "rationale"}],
        "full_reasoning": str,
      }
    """
    client = _get_client()
    indicators_text = _format_indicators_for_prompt(indicators)
    today = datetime.today().strftime("%Y-%m-%d")

    feedback_section = ""
    if feedback and feedback.strip().upper() != "CONFIRM":
        feedback_section = f"\nUser feedback to incorporate:\n{feedback}\n"

    bucket_list = "\n".join(
        f"  {b}: {ETF_UNIVERSE[b]}  (D/C={a['dc']}, G/V={a['gv']}, H/L={a['hl']}, U/E={a['ue']})"
        for b, a in BUCKET_AXES.items()
    )

    prompt = f"""You are a Chief Investment Officer making strategic asset allocation decisions as of {today}.

MACRO INDICATORS (Jan 2023 to present):
{indicators_text}
{feedback_section}

ETF UNIVERSE — 16 strategy buckets:
{bucket_list}

STEP 1 — AXIS SCORING:
Score each axis using the FULL macro picture holistically (all indicators inform all axes).
For each axis, state: which side is favored, confidence (0.0-1.0), and 2-3 sentence reasoning.

STEP 2 — FINAL ALLOCATION:
Assign a weight_pct to each of the 16 buckets.

HARD CONSTRAINTS (you must not violate these):
- All 16 weights must sum to EXACTLY 100.0
- No single bucket weight > 40%
- No sub-strategy (D, C, G, V, H, L, U, E) total > 70%
- No cash — fully invested
- Minimum weight per bucket: 0.5% (avoid zero allocations)

Respond in JSON with this EXACT structure:
{{
  "axis_scores": {{
    "defensive_cyclical": {{
      "favored": "Defensive" or "Cyclical",
      "confidence": 0.0-1.0,
      "reasoning": "..."
    }},
    "growth_value": {{
      "favored": "Growth" or "Value",
      "confidence": 0.0-1.0,
      "reasoning": "..."
    }},
    "high_low_beta": {{
      "favored": "High Beta" or "Low Beta",
      "confidence": 0.0-1.0,
      "reasoning": "..."
    }},
    "us_em": {{
      "favored": "US" or "Emerging Markets",
      "confidence": 0.0-1.0,
      "reasoning": "..."
    }}
  }},
  "allocation": [
    {{
      "strategy_bucket": "DGHU",
      "ticker": "XBI",
      "weight_pct": 6.25,
      "rationale": "one-line rationale"
    }},
    ... (all 16 buckets)
  ]
}}

Double-check: weights must sum to exactly 100.0. Sub-strategy totals must each be <= 70."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}]
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    result = json.loads(raw_text)

    axis_scores = result.get("axis_scores", {})
    allocation  = result.get("allocation", [])

    # Normalize weights to ensure they sum to exactly 100
    allocation = _normalize_weights(allocation)

    # Validate sub-strategy caps and fix if needed
    allocation = _enforce_sub_strategy_caps(allocation)

    # Persist allocation to DB
    db.save_target_allocation(allocation)

    return {
        "axis_scores":    axis_scores,
        "allocation":     allocation,
        "full_reasoning": _format_axis_reasoning(axis_scores),
    }


def _normalize_weights(allocation: list) -> list:
    # Ensures bucket weights sum to exactly 100.0 by proportional rescaling
    total = sum(row.get("weight_pct", 0) for row in allocation)
    if abs(total - 100.0) < 0.01:
        return allocation
    scale = 100.0 / total if total > 0 else 1.0
    for row in allocation:
        row["weight_pct"] = round(row["weight_pct"] * scale, 4)
    # Fix rounding residual on the largest bucket
    residual = 100.0 - sum(r["weight_pct"] for r in allocation)
    max_row = max(allocation, key=lambda r: r["weight_pct"])
    max_row["weight_pct"] = round(max_row["weight_pct"] + residual, 4)
    return allocation


def _enforce_sub_strategy_caps(allocation: list, cap: float = 70.0) -> list:
    """
    Checks sub-strategy totals (D, C, G, V, H, L, U, E) against the 70% cap.
    If any exceed the cap, proportionally reduces the offending buckets
    and redistributes to the smallest bucket in the opposing sub-strategy.
    """
    weight_map = {row["strategy_bucket"]: row for row in allocation}

    for sub, buckets in SUB_STRATEGY_AXES.items():
        total = sum(weight_map[b]["weight_pct"] for b in buckets if b in weight_map)
        if total > cap:
            excess = total - cap
            # Scale down all buckets in this sub-strategy proportionally
            for b in buckets:
                if b in weight_map:
                    weight_map[b]["weight_pct"] = round(
                        weight_map[b]["weight_pct"] * (cap / total), 4
                    )
            # Determine opposing sub and distribute excess there
            opposing_sub = _get_opposing_sub(sub)
            if opposing_sub:
                opp_buckets = SUB_STRATEGY_AXES.get(opposing_sub, [])
                if opp_buckets:
                    per_bucket = excess / len(opp_buckets)
                    for b in opp_buckets:
                        if b in weight_map:
                            weight_map[b]["weight_pct"] = round(
                                weight_map[b]["weight_pct"] + per_bucket, 4
                            )

    # Re-normalize after adjustments
    total = sum(r["weight_pct"] for r in weight_map.values())
    if abs(total - 100.0) > 0.01:
        scale = 100.0 / total
        for row in weight_map.values():
            row["weight_pct"] = round(row["weight_pct"] * scale, 4)

    return list(weight_map.values())


def _get_opposing_sub(sub: str) -> str:
    # Returns the opposing sub-strategy for redistribution
    pairs = {"D": "C", "C": "D", "G": "V", "V": "G", "H": "L", "L": "H", "U": "E", "E": "U"}
    return pairs.get(sub, "")


def _format_axis_reasoning(axis_scores: dict) -> str:
    # Formats the axis scoring breakdown as a readable multi-line string
    lines = ["AXIS SCORING BREAKDOWN", "═" * 60]
    for axis, data in axis_scores.items():
        favored    = data.get("favored", "?")
        confidence = data.get("confidence", 0)
        reasoning  = data.get("reasoning", "")
        axis_label = axis.replace("_", " / ").upper()
        lines.append(f"\n{axis_label}")
        lines.append(f"  Favored:    {favored}  (confidence: {confidence:.0%})")
        lines.append(f"  Reasoning:  {reasoning}")
    return "\n".join(lines)


def run_full_macro_analysis(feedback: str = "CONFIRM") -> dict:
    """
    Convenience wrapper: runs both phases sequentially.
    Called by the Streamlit app when INIT PORTFOLIO is clicked and then confirmed.

    Returns combined dict with keys from both phases.
    """
    print("[macro_agent] Fetching FRED indicators...")
    indicators = data_utils.get_macro_indicators()

    print("[macro_agent] Running Phase 1 — summarizing indicators...")
    phase1_result = phase1_analyze(indicators)

    print("[macro_agent] Running Phase 2 — scoring axes and allocating...")
    phase2_result = phase2_allocate(indicators, feedback=feedback)

    return {**phase1_result, **phase2_result}
