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
      className="border-l-4 border-destructive bg-red-50 px-4 py-3 text-red-700 rounded-r-md flex items-start gap-2"
      role="alert"
    >
      <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" aria-hidden="true" />
      <span className="text-sm">{t("generationFailed")}</span>
    </div>
  );
}
