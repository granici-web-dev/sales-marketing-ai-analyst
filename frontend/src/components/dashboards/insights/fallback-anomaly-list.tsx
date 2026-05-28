"use client";

import { useTranslations } from "next-intl";
import { ProblemCard } from "./problem-card";
import { Card, CardContent } from "@/components/ui/card";
import type { Problem } from "@/hooks/useInsights";

interface FallbackAnomalyListProps {
  problems: Problem[] | null;
  status: string;
}

/**
 * B6 fix — dual-mode fallback component for INSI-05.
 *
 * CASE A — status === "fallback" AND problems present:
 *   Renders a heading + ProblemCard list from payload.problems[].
 *   The GenerationFailedBanner is rendered by the PARENT page ABOVE this component.
 *
 * CASE B — status === "failed" OR problems null/empty:
 *   Renders a Card with static "Nu există date disponibile" paragraph.
 */
export function FallbackAnomalyList({ problems, status }: FallbackAnomalyListProps) {
  const t = useTranslations("insights");

  // Case A: backend generated a fallback payload from detected_problems rows
  const showProblems =
    status === "fallback" && problems !== null && problems.length > 0;

  if (showProblems) {
    return (
      <div className="space-y-3">
        <p className="text-sm font-medium text-muted-foreground mb-2">
          {t("fallbackTitle")}
        </p>
        {problems!.map((p) => (
          <ProblemCard key={p.id} problem={p} />
        ))}
      </div>
    );
  }

  // Case B: status="failed" or payload is null — no anomaly data available
  return (
    <Card>
      <CardContent className="pt-4 pb-4">
        <p className="text-sm text-muted-foreground">
          Nu există date disponibile pentru această perioadă.
        </p>
      </CardContent>
    </Card>
  );
}
