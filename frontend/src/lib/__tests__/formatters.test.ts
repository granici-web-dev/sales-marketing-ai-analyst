import { describe, it, expect } from "vitest";
import {
  formatRON,
  formatPct,
  formatDate,
  formatTimestamp,
  formatDuration,
  formatWowDelta,
  getDefaultDateRange,
} from "../formatters";

describe("formatRON", () => {
  // Use Intl.NumberFormat directly to get expected values, handling locale-specific
  // non-breaking spaces (U+00A0) that vary by Node.js ICU version.
  const intlRON = new Intl.NumberFormat("ro-RO", {
    style: "currency",
    currency: "RON",
    maximumFractionDigits: 2,
  });
  const intlRONCompact = new Intl.NumberFormat("ro-RO", {
    style: "currency",
    currency: "RON",
    maximumFractionDigits: 0,
  });

  it("formats a large integer as Romanian currency", () => {
    // 85000 → "85.000,00 RON" (with locale-correct separator)
    expect(formatRON(85000)).toBe(intlRON.format(85000));
  });

  it("returns N/A for null", () => {
    expect(formatRON(null)).toBe("N/A");
  });

  it("returns N/A for undefined", () => {
    expect(formatRON(undefined)).toBe("N/A");
  });

  it("formats a decimal string", () => {
    expect(formatRON("85000.50")).toBe(intlRON.format(85000.50));
  });

  it("formats with compact=true (0 decimal places)", () => {
    expect(formatRON(1234, true)).toBe(intlRONCompact.format(1234));
  });

  it("returns N/A for NaN string", () => {
    expect(formatRON("not-a-number")).toBe("N/A");
  });
});

describe("formatPct", () => {
  // Use Intl.NumberFormat directly — Romanian locale may use "28,5 %" with
  // a non-breaking space before the percent sign (locale-correct).
  const intlPct = new Intl.NumberFormat("ro-RO", {
    style: "percent",
    maximumFractionDigits: 1,
  });

  it("formats a decimal fraction as percentage", () => {
    // 0.285 → "28,5%" (or "28,5 %" with non-breaking space — locale-correct)
    expect(formatPct("0.285")).toBe(intlPct.format(0.285));
  });

  it("returns N/A for null", () => {
    expect(formatPct(null)).toBe("N/A");
  });

  it("returns N/A for undefined", () => {
    expect(formatPct(undefined)).toBe("N/A");
  });
});

describe("formatDate", () => {
  it("formats an ISO date string as DD.MM.YYYY", () => {
    expect(formatDate("2026-05-28")).toBe("28.05.2026");
  });

  it("returns empty string for null", () => {
    expect(formatDate(null)).toBe("");
  });

  it("returns empty string for undefined", () => {
    expect(formatDate(undefined)).toBe("");
  });

  it("returns empty string for empty string", () => {
    expect(formatDate("")).toBe("");
  });
});

describe("formatDuration", () => {
  it("formats 150 minutes as 2h 30min", () => {
    expect(formatDuration(150)).toBe("2h 30min");
  });

  it("formats 45 minutes as 45min", () => {
    expect(formatDuration(45)).toBe("45min");
  });

  it("formats exactly 60 minutes as 1h", () => {
    expect(formatDuration(60)).toBe("1h");
  });

  it("returns N/A for null", () => {
    expect(formatDuration(null)).toBe("N/A");
  });

  it("returns N/A for undefined", () => {
    expect(formatDuration(undefined)).toBe("N/A");
  });
});

describe("formatWowDelta", () => {
  it("formats a positive delta", () => {
    const result = formatWowDelta("0.12");
    expect(result.label).toBe("▲ +12.0%");
    expect(result.positive).toBe(true);
  });

  it("formats a negative delta", () => {
    const result = formatWowDelta("-0.05");
    expect(result.label).toBe("▼ -5.0%");
    expect(result.positive).toBe(false);
  });

  it("returns empty label and null for null input", () => {
    const result = formatWowDelta(null);
    expect(result.label).toBe("");
    expect(result.positive).toBeNull();
  });

  it("returns empty label and null for undefined input", () => {
    const result = formatWowDelta(undefined);
    expect(result.label).toBe("");
    expect(result.positive).toBeNull();
  });

  it("returns 0% label for zero delta", () => {
    const result = formatWowDelta("0.0");
    expect(result.label).toBe("0%");
    expect(result.positive).toBeNull();
  });
});

describe("getDefaultDateRange", () => {
  it("returns from and to as YYYY-MM-DD strings", () => {
    const range = getDefaultDateRange();
    expect(range.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(range.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("to equals today", () => {
    const range = getDefaultDateRange();
    const today = new Date().toISOString().split("T")[0];
    expect(range.to).toBe(today);
  });

  it("from is 29 days before today", () => {
    const range = getDefaultDateRange();
    const fromDate = new Date(range.from);
    const toDate = new Date(range.to);
    const diffDays = Math.round(
      (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24),
    );
    expect(diffDays).toBe(29);
  });
});
