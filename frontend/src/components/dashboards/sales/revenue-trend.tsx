"use client";

import { AreaChart, Area, XAxis, YAxis, CartesianGrid } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { TrendingUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatRON, formatDate } from "@/lib/formatters";
import type { RevenueSeries } from "@/hooks/useSalesDashboard";

interface RevenueTrendProps {
  revenueSeries: RevenueSeries[];
}

const chartConfig = {
  revenue: {
    label: "Venituri",
    color: "var(--color-accent)",
  },
} satisfies ChartConfig;

export function RevenueTrend({ revenueSeries }: RevenueTrendProps) {
  const t = useTranslations("sales");

  const isEmpty =
    !revenueSeries ||
    revenueSeries.length === 0 ||
    revenueSeries.every(
      (point) => !point.revenue || parseFloat(point.revenue) === 0,
    );

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <TrendingUp size={32} className="text-muted-foreground mb-3" aria-hidden="true" />
        <p className="text-sm font-medium text-muted-foreground">
          {t("revenue.noData")}
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
          {t("revenue.noDataDesc")}
        </p>
      </div>
    );
  }

  // Parse revenue strings to numbers for Recharts (Pitfall 3 mitigation)
  const chartData = revenueSeries.map((point) => ({
    date: point.date,
    revenue: parseFloat(point.revenue ?? "0"),
    // Short label for x-axis
    label: new Date(point.date).getDate().toString(),
  }));

  return (
    <ChartContainer config={chartConfig} className="w-full h-[200px] sm:h-[280px]">
      <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
        <defs>
          <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
            <stop
              offset="5%"
              stopColor="var(--color-accent)"
              stopOpacity={0.2}
            />
            <stop
              offset="95%"
              stopColor="var(--color-accent)"
              stopOpacity={0.02}
            />
          </linearGradient>
        </defs>
        {/* Hide grid on mobile for cleaner look */}
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="var(--border)"
          className="hidden sm:block"
        />
        <XAxis
          dataKey="label"
          axisLine={false}
          tickLine={false}
          tick={{ fontSize: 11, fill: "var(--muted-fg)" }}
          interval="preserveStartEnd"
        />
        <YAxis
          hide
          domain={["auto", "auto"]}
        />
        <ChartTooltip
          content={
            <ChartTooltipContent
              formatter={(value) => formatRON(value as number)}
            />
          }
          labelFormatter={(label) => {
            const item = chartData.find((d) => d.label === label);
            return item ? formatDate(item.date) : label;
          }}
        />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="var(--color-accent)"
          strokeWidth={2}
          fill="url(#revenueGradient)"
          dot={false}
          activeDot={{ r: 4, fill: "var(--color-accent)" }}
        />
      </AreaChart>
    </ChartContainer>
  );
}
