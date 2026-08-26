"use client";

import { useState, useEffect } from "react";
import { AlertTriangle, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useHealthData } from "@/hooks/useHealthData";
import { formatTimestamp } from "@/lib/formatters";

const DISMISSED_KEY = "freshness_dismissed";

/**
 * Shared data freshness banner driven by useHealthData().
 * Shows an amber warning when data is stale (backend reports stale=true).
 * Dismissible within the session via localStorage.
 */
export default function DataFreshnessBanner() {
  const t = useTranslations("common");
  const { data } = useHealthData();
  const [dismissed, setDismissed] = useState(false);

  // On mount: check if the banner was dismissed this session
  useEffect(() => {
    if (localStorage.getItem(DISMISSED_KEY)) {
      setDismissed(true);
    }
  }, []);

  const handleDismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "1");
    setDismissed(true);
  };

  if (!data?.stale || dismissed) {
    return null;
  }

  const lastSync = data.last_sync_at
    ? formatTimestamp(data.last_sync_at)
    : t("never");

  return (
    <div
      role="alert"
      /* Янтарная палитра Tailwind заменена токеном --warn: у неё одно
         значение на обе темы, и светлая заливка amber-50 оставалась
         светлым пятном на тёмной странице. Заливка на 12 % держит текст
         на полном токене выше 4.5:1 — тот же приём, что в badge.tsx. */
      className="mb-4 flex items-start gap-3 rounded-card border-l-4 border-warn bg-warn/12 p-4 text-warn"
    >
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-warn" />
      <p className="flex-1 text-sm">
        {t("dataStale", { lastSync })}
      </p>
      <button
        onClick={handleDismiss}
        aria-label={t("closeMenu")}
        className="ml-2 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-control hover:bg-warn/20"
      >
        <X size={16} className="text-warn" />
      </button>
    </div>
  );
}
