from __future__ import annotations

"""Number cross-check validator for Phase 5 AI Insights.

AI-06: Numbers extracted from Claude's narrative text (summary + problem descriptions)
       must match input KPI values or estimated_loss_ron values within ±2% tolerance.
       If a mismatch is found, InsightService re-generates (up to 2 retries).

Handles Romanian number formatting:
  . as thousands separator: 23.400 → 23400
  , as decimal separator:   8,3   → 8.3
  % suffix: ignored for parsing purposes
"""

import re
from decimal import Decimal


# Romanian number pattern:
# Matches: 23.400 (thousands), 8,3% (decimal comma), 351 (plain integer),
#          47.320,50 (thousands + decimal), 5.000 (plain thousands), 5050 (plain 4-digit)
#
# NOTE: The longer \d{1,3}(?:[.,]\d{3})* alternative is tried first because it handles
# thousands separators (23.400). Plain integers (\d+) are the fallback.
# Order matters: for "5050" the first alternative would only match "505" (3 digits),
# so we use a different approach — match ALL contiguous digits+separators greedily,
# then normalize in the extraction function.
NUMBER_PATTERN = re.compile(
    r"\b(\d[\d.,]*\d|\d)\b"
)


def extract_numbers_from_text(text: str) -> list[float]:
    """Extract all numeric values from Romanian-formatted narrative text.

    AI-06: Parses both Romanian formats:
      - Thousands separator: "23.400 RON" → 23400.0
      - Decimal comma: "8,3%" → 8.3
      - Plain integer: "351 lead-uri" → 351.0

    Algorithm:
      1. Find all NUMBER_PATTERN matches in text.
      2. For each match: strip thousands separators (. → ""), convert decimal comma (, → .).
      3. Parse as float and collect.

    Args:
        text: Romanian narrative text potentially containing numbers.

    Returns:
        list[float]: All extracted numeric values. May contain duplicates.
    """
    results: list[float] = []
    for match in NUMBER_PATTERN.finditer(text):
        raw = match.group(1)
        # Determine if . is a thousands separator or decimal separator:
        # If raw has multiple groups separated by . and the last group has 3 digits → thousands
        # If raw has , → comma is the decimal separator, . must be thousands
        # Examples:
        #   "23.400"  → thousands → strip "." → "23400" → 23400.0
        #   "8,3"     → decimal   → replace "," with "." → "8.3" → 8.3
        #   "47.320,50" → thousands + decimal → strip "." → "47320,50" → replace "," → "47320.50"
        #   "5.000"   → thousands → strip "." → "5000" → 5000.0

        # If contains comma, dot must be thousands separator
        if "," in raw:
            normalized = raw.replace(".", "").replace(",", ".")
        else:
            # Dot only — check if it could be thousands (3 digits after each dot)
            # Pattern: digits followed by exactly 3 digits after dot = thousands
            # e.g. "23.400" → yes; "8.3" → no (only 1 digit after dot)
            parts = raw.split(".")
            if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
                # All parts after dot have exactly 3 digits → thousands separator
                normalized = raw.replace(".", "")
            else:
                # Single dot with non-3-digit decimal → decimal point (e.g. "8.3")
                normalized = raw

        try:
            results.append(float(normalized))
        except ValueError:
            pass

    return results


def cross_check(parsed: object, kpi_snapshot: dict, problems_input: list[dict]) -> bool:
    """Cross-check numbers in Claude's narrative against input data values.

    AI-06: Verifies that numeric values in summary + problem descriptions
    are grounded in the input KPI data and anomaly estimates (±2% tolerance).

    Algorithm:
      1. Build reference set from kpi_snapshot numeric values + estimated_loss_ron values.
      2. If reference set empty → return True (no numbers to check against).
      3. Extract numbers from parsed.summary and each problem.description.
      4. For each extracted number > 10 (ignore small integers like "3 leads"):
         check if within ±2% of ANY reference value.
      5. If a number is NOT within ±2% of any reference value → return False.
      6. Return True if all narrative numbers match at least one reference value.

    ±2% formula: abs(actual - expected) / max(abs(expected), 1e-9) <= 0.02

    Args:
        parsed: DailyInsightResponse object (with .summary and .problems attributes).
        kpi_snapshot: dict of KPI field name → numeric value (may be Decimal or float).
        problems_input: list of detected_problems input dicts (with estimated_loss_ron).

    Returns:
        bool: True if all narrative numbers are grounded, False if hallucination detected.
    """
    # Build reference set — all numeric values from input data
    reference_values: list[float] = []

    # CR-02: KPI fields stored as decimals (e.g. conversion_l_to_c = 0.1080) but Claude
    # expresses them as percentages in narrative text (e.g. "10.8% conversie L→C").
    # Add the percentage-form value alongside the raw decimal so cross_check passes
    # for both representations.
    PERCENT_FIELDS = {
        "conversion_l_to_v", "conversion_v_to_o", "conversion_o_to_c",
        "conversion_l_to_c", "wow_delta_pct", "mom_delta_pct",
    }

    for key, val in kpi_snapshot.items():
        if val is not None:
            try:
                float_val = float(str(val))
                reference_values.append(float_val)
                # Also add percentage form for decimal-fraction KPI fields
                if key in PERCENT_FIELDS:
                    reference_values.append(float_val * 100)
            except (ValueError, TypeError):
                pass

    for problem in problems_input:
        loss = problem.get("estimated_loss_ron")
        if loss is not None:
            try:
                reference_values.append(float(str(loss)))
            except (ValueError, TypeError):
                pass

    # If no reference values, nothing to cross-check — trivially passes (D-13)
    if not reference_values:
        return True

    # Extract numbers from narrative text
    narrative_numbers: list[float] = []

    summary_text = getattr(parsed, "summary", "") or ""
    narrative_numbers.extend(extract_numbers_from_text(summary_text))

    problems = getattr(parsed, "problems", []) or []
    for problem in problems:
        desc = getattr(problem, "description", "") or ""
        narrative_numbers.extend(extract_numbers_from_text(desc))

    # Cross-check each narrative number > 10 against reference values
    for number in narrative_numbers:
        if number <= 10:
            # Ignore small integers (e.g., "3 lead-uri", "2 vânzători") — these are counts
            # that won't map to KPI values and would create too many false positives
            continue

        # Check if number is within ±2% of ANY reference value
        matched = False
        for ref in reference_values:
            tolerance = abs(ref) if abs(ref) > 1e-9 else 1e-9
            if abs(number - ref) / tolerance <= 0.02:
                matched = True
                break

        if not matched:
            return False

    return True
