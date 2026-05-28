---
status: partial
phase: 05-ai-insights
source: [05-VERIFICATION.md]
started: 2026-05-28T16:45:00Z
updated: 2026-05-28T16:45:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Live Claude round-trip
expected: Set ANTHROPIC_API_KEY, trigger task (or run `asyncio.run(_generate_async(TENANT_ID))`), verify `daily_insights` row inserted with `status IN ('success','fallback')`, `input_tokens > 0`, `cost_usd > 0`.
result: [pending]

### 2. Romanian language content
expected: Inspect `payload_json->>'summary'` from a live row; must contain "RON" and Romanian business vocabulary (e.g. "leads", "contracte", "vânzători").
result: [pending]

### 3. Prompt caching active
expected: Run task twice within 5 minutes; verify `cache_read_input_tokens > 0` on the second call (visible in `input_tokens` breakdown or structlog output).
result: [pending]

### 4. Fallback UI display
expected: Deferred to Phase 6 (API endpoint). The data layer is fully implemented (`daily_insights.status`, `_build_fallback()`). Verify in Phase 6 that fallback rows render correctly in the frontend.
result: [deferred to Phase 6]

## Summary

total: 4
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0
deferred: 1

## Gaps
