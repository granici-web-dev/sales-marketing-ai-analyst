"use client";

import { useTranslations } from "next-intl";
import { AlertTriangle } from "lucide-react";

/**
 * Romanian warning banner shown when InsightEnvelope.generation_failed === true.
 * This component takes no props — it is always visible when rendered.
 * INSI-05 / D-16: shown for both status="fallback" and status="failed".
 */
export function GenerationFailedBanner() {
  const t = useTranslations("insights");

  return (
    <div
      className="flex items-start gap-2 rounded-control border border-danger/30 bg-danger/10 px-4 py-3 text-danger"
      role="alert"
    >
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" aria-hidden="true" />
      <span className="text-sm">{t("generationFailed")}</span>
    </div>
  );
}
