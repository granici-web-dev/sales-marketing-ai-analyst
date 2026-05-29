// UI-SPEC § Hint helpers — pure functions used by tool-pill.tsx to render the
// secondary text on the right of a tool pill (e.g. "· 30 zile").
//
// Romanian-only by D-37 (system prompt + Claude responses are Romanian
// regardless of NEXT_LOCALE), so the helpers don't lookup i18n at the moment
// of streaming.

import { differenceInCalendarDays, parseISO } from "date-fns";

/**
 * Day count between two ISO YYYY-MM-DD dates, with Romanian noun pluralization.
 * Inclusive on both ends so "2026-05-01" → "2026-05-01" returns "1 zi", not 0.
 *
 *   dayCount("2026-05-01", "2026-05-31") → "31 zile"  (Romanian: 30..30 = 30 zile,
 *     but inclusive count over a calendar-day range; PS1: 31 days inclusive)
 *
 * Romanian pluralization rule applied here:
 *   - n == 1                    → "1 zi"
 *   - 2 <= n <= 19 (rough rule) → "N zile"     (the "few/other" plural form)
 *   - n >= 20                   → "N de zile"  (formal long form)
 *
 * UI-SPEC examples in § Tool Pill Content Rules say "30 zile" (without "de"),
 * so we use the short form for everything >= 2 to match the spec verbatim. The
 * long form is reserved for the `tools.collapsedSummary` ICU rule in i18n.
 */
export function dayCount(dateFrom: string, dateTo: string): string {
  const a = parseISO(dateFrom);
  const b = parseISO(dateTo);
  // +1 so an inclusive single-day range is "1 zi".
  const days = differenceInCalendarDays(b, a) + 1;
  if (!Number.isFinite(days) || days <= 0) {
    return "0 zile";
  }
  if (days === 1) return "1 zi";
  return `${days} zile`;
}

/**
 * Period label for a `{date_from, date_to}` tool input. Returns the canonical
 * day-count label ("30 zile"). Recognized exact ranges per UI-SPEC §
 * Tool Pill Content Rules: 7 / 30 / 90 days are special, but the rendered
 * string is still the day-count label — we don't substitute "săptămâna asta"
 * etc. because the underlying input fields are already explicit.
 */
export function periodLabel(input: { date_from: string; date_to: string }): string {
  return dayCount(input.date_from, input.date_to);
}
