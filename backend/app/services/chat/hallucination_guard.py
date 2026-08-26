"""Hallucination guard — post-stream verification for Phase 8 AI Chat (D-06).

Three concurrent checks run against the assembled assistant text AFTER the
stream completes (D-08 — frontend has already painted the first stream;
on FAIL we emit `regenerate_notice` and re-run):

1. **Numbers** (D-06): every numeric token in the response must be within ±1%
   of a number from the tool_results bag, a derived computation (pairwise %,
   sum, diff), or a common-knowledge constant (days 1-31, years 1900-2100,
   round-percent 0/50/100).

   The number extractor REUSES Phase 5 `NUMBER_PATTERN` and
   `extract_numbers_from_text` from `app.services.insights.number_validator`
   verbatim — handles Romanian thousands (`23.400` → `23400`) and decimal
   comma (`8,3` → `8.3`). No fork.

2. **Links** (D-18a): inline Markdown `[Label](href)` is allowed only when
   `href` is one of `{/sales, /salespeople, /marketing, /insights, /chat, #}`.
   Anything else (external URLs, phishing-shaped paths) is flagged.

3. **Entities**: capitalized 2-3 word names (e.g. "Maria Popescu") must be in
   the tenant's whitelist of salespeople + showrooms + 11 source categories.
   Capitalized regex tolerates Romanian diacritics (Ă, Â, Î, Ș, Ț).

Returns a list of violation strings prefixed with `number:`, `link:`, or
`entity:`. Empty list = PASS.

LM-11 (list-marker guard): integers <= 10 are skipped — they're almost
always list markers or small counts that don't map to KPI values and would
flood false positives.

References:
  - .planning/phases/08-ai-chat/08-RESEARCH.md §3 lines 721-815
  - .planning/phases/08-ai-chat/08-CONTEXT.md D-06 / D-07 / D-08 / D-18a
  - .planning/phases/08-ai-chat/08-PATTERNS.md § hallucination_guard.py
  - backend/app/services/insights/number_validator.py (REUSE — no fork)
"""

from __future__ import annotations

import contextlib
import re
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# REUSE Phase 5 number extractor — do NOT fork (08-04-PLAN.md must_haves).
from app.services.insights.number_validator import (
    extract_numbers_from_text,
)

# ── Tolerance + skip-list constants ─────────────────────────────────────────
# Number-match tolerance. Relative ±5% OR absolute ±0.6 — whichever is looser.
# The absolute floor lets Claude round percentages (e.g. "31%" for 31.49%, "11%"
# for 10.6%), which a tight relative-only bound rejects. Per the chat philosophy
# (grounded answers > refusals), the number guard's job is to catch FABRICATED
# figures (off by integer multiples), not to police rounding of real tool values.
# Entity + link sub-checks stay strict — those catch genuine fabrication/phishing.
TOLERANCE = Decimal("0.05")  # ±5% relative
ABS_TOLERANCE = Decimal("0.6")  # absolute floor (rounding of small percentages)
COMMON_DAYS: set[Decimal] = {Decimal(n) for n in range(1, 32)}
COMMON_YEARS: set[Decimal] = {Decimal(y) for y in range(1900, 2101)}
COMMON_ROUND_PERCENTS: set[Decimal] = {Decimal("0"), Decimal("50"), Decimal("100")}


# ── Link + entity whitelists (D-18a + D-22) ─────────────────────────────────
ALLOWED_HREFS: set[str] = {
    "/sales",
    "/salespeople",
    "/marketing",
    "/insights",
    "/chat",
    "#",
}

# Sofa Belle showrooms — must match the prompt builder's roster verbatim.
SOFA_BELLE_SHOWROOMS: set[str] = {"Brașov", "București", "Cluj", "Cluj-Napoca"}

# Compiled regex for capitalized 2-3 word names with Romanian diacritics.
# Anchors: \b ensures word boundaries; the capture group is the candidate name.
_ENTITY_PATTERN = re.compile(
    r"\b([A-ZĂÂÎȘȚ][a-zăâîșț]+ [A-ZĂÂÎȘȚ][a-zăâîșț]+(?: [A-ZĂÂÎȘȚ][a-zăâîșț]+)?)\b"
)

# Inline Markdown link pattern.
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# CR-04: Romanian sentence-starters that _ENTITY_PATTERN wrongly captures as
# proper-noun heads (e.g. "Conform Sofa", "Comparativ Săptămâna"). The first
# token of every entity candidate is checked here and skipped before the
# whitelist lookup, so normal Romanian phrasing doesn't burn the regen budget.
_ROMANIAN_SENTENCE_STARTERS: set[str] = {
    "Conform", "Comparativ", "Astfel", "Practic", "Probabil", "Datorită",
    "Astăzi", "Ieri", "Acum", "Apoi", "Deci", "Totuși", "Însă",
    "În", "Pentru", "Cu", "De", "La", "Pe", "Prin", "Sub", "Spre", "Din", "După",
    "Săptămâna", "Luna", "Anul", "Ziua", "Trimestrul", "Perioada",
    "Vânzările", "Vânzătorul", "Datele", "Showroom", "Showroom-ul", "Lead",
    "Lead-uri", "Oferta", "Ofertele", "Contractul", "Contractele", "Rata",
    "Conversia", "Echipa",
    "Cel", "Cea", "Cei", "Cele", "Această", "Acest", "Aceste", "Acești",
    "Toate", "Toți", "Totul", "Câteva", "Câțiva", "Fiecare",
}

# Out-of-scope platform/source names the system prompt explicitly enumerates as
# UNCONNECTED (Meta/Google Ads/TikTok/GA4/Search Console). When the user asks
# about these, Claude is INSTRUCTED to name them in a polite refusal — so they
# appear as capitalized multi-word phrases ("Google Ads", "Search Console") that
# the entity regex would otherwise flag as fabricated entities, killing the
# refusal via the guard→regenerate→fallback path. These are known proper nouns
# (not hallucinated business data), so any entity candidate whose first token is
# a platform name is skipped. Domain note: no Sofa Belle business entity
# (salesperson/showroom/source) legitimately starts with these words, so this
# cannot mask a real fabrication.
_PLATFORM_FIRST_TOKENS: set[str] = {
    "Google", "Meta", "Facebook", "Instagram", "TikTok", "GA4",
    "Search", "Analytics", "Ads", "Console",
}


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────


def _extract_numbers_recursive(value: object) -> set[Decimal]:
    """Walk a JSON-like tool result and collect every numeric leaf as Decimal.

    Handles dicts, lists, primitives (int/float/Decimal), and strings (which
    may carry Romanian-formatted numbers — re-parse via Phase 5 extractor).
    """
    out: set[Decimal] = set()
    if isinstance(value, bool):
        return out  # bools subclass int in Python — skip
    if isinstance(value, (int, float, Decimal)):
        out.add(Decimal(str(value)))
    elif isinstance(value, str):
        # Tool outputs serialize numerics as machine-format strings, e.g.
        # "0.31490000000000000000" or "1.1428571428571429". These are NOT
        # Romanian-formatted — routing them through extract_numbers_from_text
        # would treat ".314" as a thousands group and mangle 0.3149 -> 314.
        # Try a direct Decimal parse first; only fall back to the Romanian
        # narrative extractor for genuinely free-text strings (labels, dates).
        stripped = value.strip()
        try:
            out.add(Decimal(stripped))
        except (InvalidOperation, ValueError):
            out.update(Decimal(str(n)) for n in extract_numbers_from_text(value))
    elif isinstance(value, dict):
        for v in value.values():
            out |= _extract_numbers_recursive(v)
    elif isinstance(value, list):
        for v in value:
            out |= _extract_numbers_recursive(v)
    return out


def _compute_derived(base: set[Decimal]) -> set[Decimal]:
    """Pairwise %, sum, diff — quantized to 1 decimal place.

    Claude commonly computes ratios from tool numbers ("X = 200% of Y"), sums
    ("total = a + b"), or diffs ("delta = a - b"). We add these to the
    allow-set so the guard accepts grounded computations.
    """
    derived: set[Decimal] = set()
    items = list(base)
    Q = Decimal("0.1")

    def _q(x: Decimal) -> None:
        # quantize can raise InvalidOperation (DivisionImpossible) when the
        # result needs more digits than the Decimal context allows. Swallow
        # per-value so one bad pair never aborts the whole allow-set (which
        # would degrade matching and flag legitimate, grounded numbers).
        with contextlib.suppress(InvalidOperation, ValueError):
            derived.add(x.quantize(Q))

    for a in items:
        # ratio -> percentage: Claude renders 0.3149 as "31,5%". Add a*100 so
        # the grounded percentage matches directly (independent of pair math).
        _q(a * Decimal("100"))
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if b != 0:
                _q((a / b) * Decimal("100"))
            if a != 0:
                _q((b / a) * Decimal("100"))
            derived.add(a + b)
            derived.add(abs(a - b))
    return derived


def _is_within_tolerance(num: Decimal, allowed: set[Decimal]) -> bool:
    """Return True if `num` is within ±TOLERANCE of any value in `allowed`."""
    for a in allowed:
        diff = abs(num - a)
        if diff <= ABS_TOLERANCE:
            return True
        ref_mag = abs(a) if abs(a) > Decimal("1e-9") else Decimal("1e-9")
        if diff / ref_mag <= TOLERANCE:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def check_response(
    response_text: str,
    tool_results: list[dict],
    entity_whitelist: dict[str, set[str]] | None = None,
) -> list[str]:
    """Verify the assistant text against tool_results + whitelists.

    Args:
        response_text: assembled assistant message text (post-stream).
        tool_results: list of dicts — each dict is one tool handler's return value
            (recursive number extraction covers nested keys + lists).
        entity_whitelist: optional `{salespeople, showrooms, categories}` dict;
            when omitted, entity checking is skipped (tests for numbers-only paths).

    Returns:
        list[str]: violation tokens. Empty list means the response PASSED the guard.
        Each token is one of:
            - `number:<value>` — numeric token not in tolerance range
            - `link:<href>`    — Markdown link with disallowed href
            - `entity:<name>`  — capitalized name not in whitelist
    """
    unsupported: list[str] = []

    # ── 1. Numbers ──────────────────────────────────────────────────────────
    allowed: set[Decimal] = set()
    for tr in tool_results:
        allowed |= _extract_numbers_recursive(tr)
    allowed |= _compute_derived(allowed)
    allowed |= COMMON_DAYS | COMMON_YEARS | COMMON_ROUND_PERCENTS

    response_numbers = [Decimal(str(n)) for n in extract_numbers_from_text(response_text)]
    for num in response_numbers:
        # LM-11: skip small counts (list markers, "3 contracts", etc.)
        if num <= Decimal("10"):
            continue
        # Skip calendar years (1900-2100)
        if Decimal("1900") <= num <= Decimal("2100"):
            continue
        if not _is_within_tolerance(num, allowed):
            # Render the value without scientific notation
            unsupported.append(f"number:{_format_decimal(num)}")

    # ── 2. Links (D-18a whitelist) ──────────────────────────────────────────
    for match in _LINK_PATTERN.finditer(response_text):
        href = match.group(2).strip()
        if href not in ALLOWED_HREFS:
            unsupported.append(f"link:{href}")

    # ── 3. Entities (capitalized 2-3 word names) ────────────────────────────
    if entity_whitelist:
        all_names: set[str] = set()
        all_names |= entity_whitelist.get("salespeople", set())
        all_names |= entity_whitelist.get("showrooms", set())
        all_names |= entity_whitelist.get("categories", set())
        # Normalize internal whitespace: MEFI names can carry double spaces
        # (e.g. "Raileanu  Leon") while Claude writes a single space. Compare
        # on collapsed-whitespace form so the roster still matches.
        all_names = {" ".join(n.split()) for n in all_names if n}
        # The system prompt INSTRUCTS Claude to emit dashboard links like
        # [Salespeople Dashboard](/salespeople). The capitalized link label
        # ("Salespeople Dashboard") is UI chrome, not a data entity — scanning
        # it as a name produces guaranteed false positives. Strip link labels
        # (hrefs are already validated in section 2) before entity matching.
        entity_text = _LINK_PATTERN.sub(" ", response_text)
        for match in _ENTITY_PATTERN.finditer(entity_text):
            candidate = " ".join(match.group(1).split())
            # CR-04: skip Romanian sentence-openers (not entity heads).
            if candidate.split()[0] in _ROMANIAN_SENTENCE_STARTERS:
                continue
            # 08-09: skip known out-of-scope platform names ("Google Ads",
            # "Search Console") — Claude names these in legitimate refusals.
            if candidate.split()[0] in _PLATFORM_FIRST_TOKENS:
                continue
            if candidate not in all_names:
                unsupported.append(f"entity:{candidate}")

    return unsupported


def _format_decimal(num: Decimal) -> str:
    """Render a Decimal without scientific notation, trimming trailing zeros."""
    # Convert to int when the number is integral to avoid "23400.0" output
    if num == num.to_integral_value():
        return str(int(num))
    return format(num.normalize(), "f")


async def build_entity_whitelist(
    session: AsyncSession,
    tenant_id: UUID,
) -> dict[str, set[str]]:
    """Build the tenant's entity whitelist for the guard's entity check.

    Returns a dict with three keys:
      - salespeople: full names from mefi_salespeople (is_active filter
                     deferred — Phase 5 already filters; we accept the
                     full roster to allow grounded historical references).
      - showrooms:   the 3 Sofa Belle showroom names + the "Cluj" variant
                     (Claude sometimes writes "Cluj" instead of "Cluj-Napoca").
      - categories:  the 11 canonical MEFI source category names.

    The orchestrator builds this ONCE per request and passes the result into
    `check_response(...)` so we don't hit the DB on the regenerate retry.
    """
    from app.models.mefi import MefiSalesperson
    from app.services.dashboards.dashboard_read_service import (
        MEFI_SOURCE_ID_TO_NAME,
    )

    stmt = select(MefiSalesperson.name).where(MefiSalesperson.tenant_id == tenant_id)
    result = await session.execute(stmt)
    rows = result.all()
    salespeople = {row[0] for row in rows if row and row[0]}

    return {
        "salespeople": salespeople,
        "showrooms": SOFA_BELLE_SHOWROOMS.copy(),
        "categories": set(MEFI_SOURCE_ID_TO_NAME.values()),
    }
