"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  useSalespeopleDashboard,
} from "@/hooks/useSalespeopleDashboard";
import { getDefaultDateRange } from "@/lib/formatters";
import { DateRangePicker } from "@/components/date-range-picker";
import { LeaderboardTable } from "@/components/dashboards/salespeople/leaderboard-table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

function InlineError({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("common");
  return (
    <div className="flex flex-col items-center gap-2 py-8">
      <p className="text-sm text-red-600">{t("error")}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {t("retry")}
      </Button>
    </div>
  );
}

function SalespeoplePageContent() {
  const t = useTranslations("salespeople");
  const searchParams = useSearchParams();
  const defaults = getDefaultDateRange();

  // T-7-06 mitigation: validate URL date params, fall back to defaults on invalid
  const rawFrom = searchParams.get("from") ?? defaults.from;
  const rawTo = searchParams.get("to") ?? defaults.to;
  const fromDate = new Date(rawFrom);
  const toDate = new Date(rawTo);
  const from = isNaN(fromDate.getTime()) ? defaults.from : rawFrom;
  const to = isNaN(toDate.getTime()) ? defaults.to : rawTo;

  const { data, isLoading, isError, refetch } = useSalespeopleDashboard(
    from,
    to,
  );

  return (
    <div className="space-y-6">
      {/* Header row: page title + date picker */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-[hsl(240_10%_4%)]">
          {t("title")}
        </h1>
        <Suspense fallback={<Skeleton className="h-10 w-64" />}>
          <DateRangePicker />
        </Suspense>
      </div>

      {/* Leaderboard section */}
      {isLoading ? (
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <Skeleton key={i} className="h-[44px] w-full" />
          ))}
        </div>
      ) : isError ? (
        <InlineError onRetry={() => refetch()} />
      ) : data ? (
        <LeaderboardTable salespeople={data.salespeople} />
      ) : null}
    </div>
  );
}

export default function SalespeopePage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <SalespeoplePageContent />
    </Suspense>
  );
}
