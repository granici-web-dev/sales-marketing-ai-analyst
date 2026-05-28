"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface LeadVolumeBySourcePoint {
  date: string;
  leads: number | null;
}

export interface LeadVolumeBySource {
  source: string;
  total_leads: number | null;
  series: LeadVolumeBySourcePoint[];
}

export interface JunkBySource {
  source: string;
  junk_count: number | null;
  total_leads: number | null;
  junk_pct: string | null;
}

export interface MarketingDashboardData {
  period: { from: string; to: string };
  lead_volume_by_source: LeadVolumeBySource[];
  site_conversion_rate: string | null;
  junk_by_source: JunkBySource[];
  ad_spend: null;
  cpl: null;
  cac: null;
  roas: null;
}

export function useMarketingDashboard(from: string, to: string) {
  return useQuery<MarketingDashboardData>({
    queryKey: ["marketing", from, to],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/dashboards/marketing?from=${from}&to=${to}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(from && to),
  });
}
