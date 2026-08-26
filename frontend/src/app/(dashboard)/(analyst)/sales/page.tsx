"use client";

import { Suspense } from "react";
import { useTranslations } from "next-intl";
import { useSalesDashboard } from "@/hooks/useSalesDashboard";
import { useUrlDateRange } from "@/hooks/useUrlDateRange";
import { DateRangePicker } from "@/components/date-range-picker";
import { KpiCards } from "@/components/dashboards/sales/kpi-cards";
import { FunnelChart } from "@/components/dashboards/sales/funnel-chart";
import { SourceBreakdown } from "@/components/dashboards/sales/source-breakdown";
import { RevenueTrend } from "@/components/dashboards/sales/revenue-trend";
import { StuckOffers } from "@/components/dashboards/sales/stuck-offers";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function InlineError({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("common");
  return (
    <div className="flex flex-col items-center gap-2 py-8">
      <p className="text-sm text-danger">{t("error")}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        {t("retry")}
      </Button>
    </div>
  );
}

function SalesPageContent() {
  const t = useTranslations("sales");
  // useUrlDateRange reads window.location.search on mount (bulletproof initial
  // value) and syncs to searchParams afterwards (T-7-01 + validates YMD format).
  const { from, to } = useUrlDateRange();

  const { data, isLoading, isError, refetch } = useSalesDashboard(from, to);

  return (
    <div className="space-y-6">
      {/* Header row: page title + date picker */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold text-foreground">
          {t("title")}
        </h1>
        <Suspense fallback={<Skeleton className="h-10 w-64" />}>
          <DateRangePicker />
        </Suspense>
      </div>

      {/* Section 1: KPI Cards */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-[100px] w-full rounded-lg" />
          ))}
        </div>
      ) : isError ? (
        <InlineError onRetry={() => refetch()} />
      ) : data ? (
        <KpiCards kpiCards={data.kpi_cards} />
      ) : null}

      {/* Section 2: Funnel Chart */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            {t("funnel.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <FunnelChart
              funnel={data.funnel}
              conversion_rates={data.conversion_rates}
            />
          ) : null}
        </CardContent>
      </Card>

      {/* Section 3: Source Breakdown */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            {t("sources.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <SourceBreakdown sourceBreakdown={data.source_breakdown} />
          ) : null}
        </CardContent>
      </Card>

      {/* Section 4: Revenue Trend */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            {t("revenue.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[200px] w-full" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <RevenueTrend revenueSeries={data.revenue_series} />
          ) : null}
        </CardContent>
      </Card>

      {/* Section 5: Stuck Offers */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">
            {t("stuckOffers.title")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[120px] w-full" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <StuckOffers stuckOffers={data.stuck_offers} />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

export default function SalesPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <SalesPageContent />
    </Suspense>
  );
}
