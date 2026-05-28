"use client";

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface HealthDataResponse {
  last_sync_at: string | null;
  last_pipeline_status: string | null;
  stale: boolean;
}

/**
 * TanStack Query hook for /api/v1/health/data.
 * Uses staleTime of 60s (more frequent than the default 5min — freshness needs more frequent refresh).
 */
export function useHealthData() {
  return useQuery<HealthDataResponse>({
    queryKey: ["health", "data"],
    queryFn: async () => {
      const res = await apiClient.get("/api/v1/health/data");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<HealthDataResponse>;
    },
    staleTime: 60 * 1000, // 60 seconds — overrides layout default of 5min
  });
}
