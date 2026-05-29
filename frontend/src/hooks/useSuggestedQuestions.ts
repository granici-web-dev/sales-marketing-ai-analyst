"use client";

// Phase 8 D-17 — suggested-question chips. Backend returns 5 static + 0..2
// dynamic. On any error the hook falls back silently to an empty array — the
// UI treats chips as nice-to-have and never blocks input.

import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type SuggestedContext =
  | "homepage"
  | "sales"
  | "salespeople"
  | "marketing"
  | "insights";

export interface SuggestedQuestionsResponse {
  questions: string[];
}

export function useSuggestedQuestions(context: SuggestedContext = "homepage") {
  return useQuery<string[]>({
    queryKey: ["chat", "suggested-questions", context],
    queryFn: async () => {
      try {
        const res = await apiClient.get(
          `/api/v1/chat/suggested-questions?context=${context}`,
        );
        if (!res.ok) return [];
        const data = (await res.json()) as
          | SuggestedQuestionsResponse
          | string[];
        if (Array.isArray(data)) return data;
        return Array.isArray(data.questions) ? data.questions : [];
      } catch {
        // D-17 fault tolerance: chips never block the input.
        return [];
      }
    },
    staleTime: 5 * 60_000, // 5 min — chips don't change often
    retry: false,
  });
}
