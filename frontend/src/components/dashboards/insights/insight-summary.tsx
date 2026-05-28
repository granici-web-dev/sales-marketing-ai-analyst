"use client";

import { useTranslations } from "next-intl";
import { formatDate } from "@/lib/formatters";

interface InsightSummaryProps {
  summary: string;
  insightDate: string; // InsightEnvelope.date — display this, NOT new Date() (Pitfall 8)
}

/**
 * Renders the AI-generated daily summary paragraph.
 * W8 fix: uses props.summary (NOT payload.summary_ro — that field does not exist).
 */
export function InsightSummary({ summary, insightDate }: InsightSummaryProps) {
  const t = useTranslations("insights");

  return (
    <div className="space-y-2">
      <p className="text-sm text-muted-foreground font-medium">
        {t("summary.heading")}
      </p>
      {/* B3: render props.summary — the caller must pass payload.summary, never payload.summary_ro */}
      <p className="text-sm leading-relaxed">{summary}</p>
      <p className="text-xs text-muted-foreground">
        {t("summary.dataFor")} {formatDate(insightDate)}
      </p>
    </div>
  );
}
