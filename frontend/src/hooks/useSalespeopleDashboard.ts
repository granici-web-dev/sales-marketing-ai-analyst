"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface SalespersonRow {
  external_id: string;
  name: string | null;
  leads_assigned: number | null;
  visits_conducted: number | null;
  offers_sent: number | null;
  deals_won: number | null;
  revenue: string | null;
  avg_deal_size: string | null;
  win_rate: string | null;
  /** Integer minutes — NOT string. Red highlight when > 240. */
  avg_time_to_first_touch_minutes: number | null;
  data_completeness_pct: string | null;
  conversion_l_to_v: string | null;
  conversion_v_to_o: string | null;
  conversion_o_to_c: string | null;
  conversion_l_to_c: string | null;
}

export interface SalespeopleDashboardData {
  period: { from: string; to: string };
  salespeople: SalespersonRow[];
}

export function useSalespeopleDashboard(from: string, to: string) {
  return useQuery<SalespeopleDashboardData>({
    queryKey: ["salespeople", from, to],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/dashboards/salespeople?from=${from}&to=${to}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(from && to),
  });
}
