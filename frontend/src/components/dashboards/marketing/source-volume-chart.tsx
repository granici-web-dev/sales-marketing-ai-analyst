"use client";

import { LineChart, Line, XAxis, YAxis, CartesianGrid } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  ChartLegend,
  ChartLegendContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { TrendingUp } from "lucide-react";
import { useTranslations } from "next-intl";
import type { LeadVolumeBySource } from "@/hooks/useMarketingDashboard";

interface SourceVolumeChartProps {
  leadVolumeBySource: LeadVolumeBySource[];
}

/** Sanitize a source name for use as an object property key */
function toSafeKey(source: string): string {
  return source.replace(/\W/g, "_");
}

/** Build a flat pivoted array for Recharts from per-source series arrays */
function pivotData(
  sources: LeadVolumeBySource[],
): Record<string, string | number | null>[] {
  if (sources.length === 0) return [];

  // Collect all unique dates across all source series
  const dateSet = new Set<string>();
  for (const src of sources) {
    for (const point of src.series) {
      dateSet.add(point.date);
    }
  }

  const sortedDates = Array.from(dateSet).sort();

  return sortedDates.map((date) => {
    const row: Record<string, string | number | null> = { date };
    for (const src of sources) {
      const key = toSafeKey(src.source);
      const point = src.series.find((p) => p.date === date);
      row[key] = point?.leads ?? null;
    }
    return row;
  });
}

/**
 * Цвета рядов. Все шесть — токены: у каждого своё значение в светлой теме
 * и в тёмной, иначе половина рядов выцветает на тёмном фоне до неразличимости.
 */
const SERIES_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
];

export function SourceVolumeChart({ leadVolumeBySource }: SourceVolumeChartProps) {
  const t = useTranslations("marketing");

  // Empty state: no sources or all series are empty
  const hasData =
    leadVolumeBySource.length > 0 &&
    leadVolumeBySource.some((src) => src.series.length > 0);

  if (!hasData) {
    return (
      <div className="flex min-h-[200px] flex-col items-center justify-center py-12 text-center">
        <TrendingUp
          size={32}
          className="mb-3 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-muted-foreground">
          {t("sourceVolume.noData")}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {t("sourceVolume.noDataDesc")}
        </p>
      </div>
    );
  }

  const data = pivotData(leadVolumeBySource);

  // Build ChartConfig dynamically from source list
  const chartConfig: ChartConfig = {};
  leadVolumeBySource.forEach((src, idx) => {
    const key = toSafeKey(src.source);
    chartConfig[key] = {
      label: src.source,
      color: SERIES_COLORS[idx % SERIES_COLORS.length],
    };
  });

  return (
    <div>
      {/* Desktop: show legend */}
      <div className="hidden sm:block">
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(val: string) => {
                // Show DD.MM format
                const parts = val.split("-");
                if (parts.length === 3) {
                  return `${parts[2]}.${parts[1]}`;
                }
                return val;
              }}
            />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            {leadVolumeBySource.map((src) => {
              const key = toSafeKey(src.source);
              return (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={`var(--color-${key})`}
                  dot={false}
                  strokeWidth={2}
                  connectNulls
                />
              );
            })}
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
          </LineChart>
        </ChartContainer>
      </div>

      {/* Mobile: hide legend and gridlines, simplified axes */}
      <div className="block sm:hidden">
        <ChartContainer config={chartConfig} className="h-[200px] w-full">
          <LineChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10 }}
              tickFormatter={(val: string) => {
                const parts = val.split("-");
                if (parts.length === 3) {
                  return parts[2]; // day only on mobile
                }
                return val;
              }}
            />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} width={24} />
            {leadVolumeBySource.map((src) => {
              const key = toSafeKey(src.source);
              return (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={`var(--color-${key})`}
                  dot={false}
                  strokeWidth={2}
                  connectNulls
                />
              );
            })}
            <ChartTooltip content={<ChartTooltipContent />} />
          </LineChart>
        </ChartContainer>
      </div>
    </div>
  );
}
