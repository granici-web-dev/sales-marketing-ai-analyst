"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface FunnelCounts {
  leads: number | null;
  visits: number | null;
  offers: number | null;
  contracts: number | null;
}

export interface ConversionRates {
  l_to_v: string | null;
  v_to_o: string | null;
  l_to_o: string | null;
  o_to_c: string | null;
  l_to_c: string | null;
  l_to_v_wow_delta: string | null;
  v_to_o_wow_delta: string | null;
  l_to_o_wow_delta: string | null;
  o_to_c_wow_delta: string | null;
  l_to_c_wow_delta: string | null;
  l_to_v_mom_delta: string | null;
  v_to_o_mom_delta: string | null;
  l_to_o_mom_delta: string | null;
  o_to_c_mom_delta: string | null;
  l_to_c_mom_delta: string | null;
}

export interface KpiCards {
  leads_total: number | null;
  visits_count: number | null;
  offers_count: number | null;
  contracts_count: number | null;
  revenue: string | null;
  avg_deal_size: string | null;
  revenue_wow_delta: string | null;
  revenue_mom_delta: string | null;
  leads_total_wow_delta: string | null;
  leads_total_mom_delta: string | null;
}

export interface SourceBreakdownItem {
  source: string;
  leads: number | null;
  visits: number | null;
  offers: number | null;
  deals_won: number | null;
  revenue: string | null;
  conversion_rate: string | null;
}

export interface RevenueSeries {
  date: string;
  revenue: string | null;
}

export interface StuckOffer {
  external_id: string;
  days_stuck: number;
  salesperson_name: string | null;
}

export interface SalesDashboardData {
  period: { from: string; to: string };
  funnel: FunnelCounts;
  conversion_rates: ConversionRates;
  kpi_cards: KpiCards;
  source_breakdown: SourceBreakdownItem[];
  revenue_series: RevenueSeries[];
  stuck_offers: StuckOffer[];
}

export function useSalesDashboard(from: string, to: string) {
  return useQuery<SalesDashboardData>({
    queryKey: ["sales", from, to],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/dashboards/sales?from=${from}&to=${to}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(from && to),
  });
}
