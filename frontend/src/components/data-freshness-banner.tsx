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
      className="mb-4 flex items-start gap-3 rounded-md border-l-4 border-amber-500 bg-amber-50 p-4 text-amber-800"
    >
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-600" />
      <p className="flex-1 text-sm">
        {t("dataStale", { lastSync })}
      </p>
      <button
        onClick={handleDismiss}
        aria-label={t("closeMenu")}
        className="ml-2 flex min-h-[44px] min-w-[44px] items-center justify-center rounded-md hover:bg-amber-100"
      >
        <X size={16} className="text-amber-700" />
      </button>
    </div>
  );
}
