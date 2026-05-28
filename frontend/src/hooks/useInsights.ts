"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// ─── Types ─────────────────────────────────────────────────────────────────

export interface ActionItem {
  order: number;
  description: string;
  owner: string;
  deadline: "Azi" | "Mâine" | "Săptămâna aceasta" | "Luna aceasta";
  expected_outcome: string;
}

export interface Problem {
  id: string; // = rule_id from detected_problems (INSI-04 source traceability)
  severity: "high" | "medium" | "low";
  category: "marketing" | "sales" | "team" | "funnel";
  title: string;
  description: string;
  estimated_loss_ron: number; // Decimal in Python but arrives as number per Assumption A2
  actions: ActionItem[];
}

export interface Positive {
  title: string;
  description: string;
  recommendation: string;
}

export interface Warning {
  title: string;
  description: string;
}

export interface InsightPayload {
  summary: string; // B3 CRITICAL: field is "summary" NOT "summary_ro" — verified from daily_insight_schema.py
  problems: Problem[]; // max 3
  positives: Positive[];
  warnings: Warning[];
  weekly_action_plan: string[];
  generated_at: string;
}

export interface InsightEnvelope {
  date: string; // YYYY-MM-DD — display this, NOT new Date() (Pitfall 8)
  status: string; // "success" | "failed" | "fallback" | "running"
  generation_failed: boolean; // true when status in ("failed", "fallback")
  generated_at: string | null;
  payload: InsightPayload | null;
}

// ─── Hooks ──────────────────────────────────────────────────────────────────

/**
 * INSI-01: Fetch today's insight envelope.
 */
export function useInsightsToday() {
  return useQuery<InsightEnvelope>({
    queryKey: ["insights", "today"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/insights/today");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
  });
}

/**
 * INSI-02: Fetch a historical insight by YYYY-MM-DD date.
 * Returns null on 404 (no insight for that date) — not an error.
 */
export function useInsightsByDate(date: string | null) {
  return useQuery<InsightEnvelope | null>({
    queryKey: ["insights", date],
    queryFn: async () => {
      const res = await apiClient.get(`/api/v1/insights?date=${date}`);
      if (res.status === 404) return null; // 404 = no insight for that date
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(date),
  });
}

/**
 * INSI-03: Trigger a manual pipeline refresh.
 * W10 fix — uses useMutation (not a raw async function).
 * On 429: returns { ok: false, retryAfterSeconds } from Retry-After header.
 * On 2xx: invalidates the "insights today" query.
 */
export function useInsightsRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (): Promise<{
      ok: boolean;
      retryAfterSeconds: number | null;
    }> => {
      const res = await apiClient.post("/api/v1/insights/refresh", {});
      if (res.status === 429) {
        // Parse Retry-After header (in seconds) per INSI-03
        const retryAfter = parseInt(
          res.headers.get("Retry-After") ?? "0",
          10,
        );
        return { ok: false, retryAfterSeconds: retryAfter };
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return { ok: true, retryAfterSeconds: null };
    },
    onSuccess: (data) => {
      if (data.ok) {
        queryClient.invalidateQueries({ queryKey: ["insights", "today"] });
      }
    },
  });
}
