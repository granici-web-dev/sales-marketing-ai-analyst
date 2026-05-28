"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useMarketingDashboard } from "@/hooks/useMarketingDashboard";
import { formatPct, getDefaultDateRange } from "@/lib/formatters";
import { DateRangePicker } from "@/components/date-range-picker";
import { SourceVolumeChart } from "@/components/dashboards/marketing/source-volume-chart";
import { JunkPctTable } from "@/components/dashboards/marketing/junk-pct-table";
import { AdSpendPlaceholder } from "@/components/dashboards/marketing/ad-spend-placeholder";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

function MarketingPageContent() {
  const t = useTranslations("marketing");
  const searchParams = useSearchParams();
  const defaults = getDefaultDateRange();

  // T-7-10 mitigation: validate URL date params, fall back to defaults on invalid
  const rawFrom = searchParams.get("from") ?? defaults.from;
  const rawTo = searchParams.get("to") ?? defaults.to;
  const fromDate = new Date(rawFrom);
  const toDate = new Date(rawTo);
  const from = isNaN(fromDate.getTime()) ? defaults.from : rawFrom;
  const to = isNaN(toDate.getTime()) ? defaults.to : rawTo;

  const { data, isLoading, isError, refetch } = useMarketingDashboard(from, to);

  return (
    <div className="space-y-6">
      {/* Header row: page title + date picker */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-semibold text-[hsl(240_10%_4%)]">
          {t("title")}
        </h1>
        <Suspense fallback={<Skeleton className="h-10 w-64" />}>
          <DateRangePicker />
        </Suspense>
      </div>

      {/* Section 1: Source volume chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("sourceVolume.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-[260px] w-full" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <SourceVolumeChart
              leadVolumeBySource={data.lead_volume_by_source}
            />
          ) : null}
        </CardContent>
      </Card>

      {/* Section 2: Site conversion rate */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("siteConversion.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-12 w-32" />
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <p className="text-3xl font-bold text-[hsl(240_10%_4%)]">
              {data.site_conversion_rate !== null
                ? formatPct(data.site_conversion_rate)
                : "N/A"}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {/* Section 3: Junk % by source table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">{t("junk.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              {[...Array(4)].map((_, i) => (
                <Skeleton key={i} className="h-[40px] w-full" />
              ))}
            </div>
          ) : isError ? (
            <InlineError onRetry={() => refetch()} />
          ) : data ? (
            <JunkPctTable junkBySource={data.junk_by_source} />
          ) : null}
        </CardContent>
      </Card>

      {/* Section 4: Ad spend placeholder — always rendered (MARK-03) */}
      <AdSpendPlaceholder />
    </div>
  );
}

export default function MarketingPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <MarketingPageContent />
    </Suspense>
  );
}
