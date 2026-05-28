"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { getDefaultDateRange } from "@/lib/formatters";

function isValidYmd(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const d = new Date(value);
  return !isNaN(d.getTime());
}

function readFromLocation(): { from: string | null; to: string | null } {
  if (typeof window === "undefined") return { from: null, to: null };
  const params = new URLSearchParams(window.location.search);
  return {
    from: params.get("from"),
    to: params.get("to"),
  };
}

/**
 * Read date range from URL with bulletproof initial-render handling.
 *
 * Next.js App Router's useSearchParams() can return an empty snapshot during
 * the first client render after hydration, causing data hooks to fire with
 * default values instead of URL values. We initialize state from
 * window.location.search directly (always populated on the client) and then
 * sync via useEffect when searchParams change (e.g., router.push from the
 * DateRangePicker).
 */
export function useUrlDateRange(): { from: string; to: string } {
  const searchParams = useSearchParams();

  const [range, setRange] = useState<{ from: string; to: string }>(() => {
    const defaults = getDefaultDateRange();
    const loc = readFromLocation();
    return {
      from: loc.from && isValidYmd(loc.from) ? loc.from : defaults.from,
      to: loc.to && isValidYmd(loc.to) ? loc.to : defaults.to,
    };
  });

  useEffect(() => {
    const defaults = getDefaultDateRange();
    const urlFrom = searchParams.get("from");
    const urlTo = searchParams.get("to");
    // Prefer searchParams (reactive), fall back to window.location, then defaults
    const loc = readFromLocation();
    const nextFrom =
      urlFrom && isValidYmd(urlFrom)
        ? urlFrom
        : loc.from && isValidYmd(loc.from)
          ? loc.from
          : defaults.from;
    const nextTo =
      urlTo && isValidYmd(urlTo)
        ? urlTo
        : loc.to && isValidYmd(loc.to)
          ? loc.to
          : defaults.to;
    setRange((prev) =>
      prev.from === nextFrom && prev.to === nextTo
        ? prev
        : { from: nextFrom, to: nextTo },
    );
  }, [searchParams]);

  return range;
}
