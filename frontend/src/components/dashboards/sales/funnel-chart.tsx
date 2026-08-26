"use client";

import { BarChart, Bar, XAxis, YAxis, LabelList } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Badge } from "@/components/ui/badge";
import { BarChart3 } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatWowDelta, formatPct } from "@/lib/formatters";
import type { FunnelCounts, ConversionRates } from "@/hooks/useSalesDashboard";

interface FunnelChartProps {
  funnel: FunnelCounts;
  conversion_rates: ConversionRates;
}

const chartConfig = {
  count: {
    label: "Număr",
    color: "var(--color-accent)",
  },
} satisfies ChartConfig;

export function FunnelChart({ funnel, conversion_rates }: FunnelChartProps) {
  const t = useTranslations("sales");

  const isEmpty =
    funnel.leads === null || funnel.leads === 0;

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <BarChart3 size={32} className="text-muted-foreground mb-3" aria-hidden="true" />
        <p className="text-sm font-medium text-muted-foreground">
          {t("funnel.noData")}
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
          {t("funnel.noDataDesc")}
        </p>
      </div>
    );
  }

  const chartData = [
    {
      stage: t("funnel.stages.lead"),
      count: funnel.leads ?? 0,
      wowDelta: conversion_rates.l_to_v_wow_delta,
      conversion: null,
    },
    {
      stage: t("funnel.stages.visit"),
      count: funnel.visits ?? 0,
      wowDelta: conversion_rates.v_to_o_wow_delta,
      conversion: conversion_rates.l_to_v,
    },
    {
      stage: t("funnel.stages.offer"),
      count: funnel.offers ?? 0,
      wowDelta: conversion_rates.l_to_o_wow_delta,
      conversion: conversion_rates.v_to_o,
    },
    {
      stage: t("funnel.stages.contract"),
      count: funnel.contracts ?? 0,
      wowDelta: null,
      conversion: conversion_rates.o_to_c,
    },
  ];

  const mobileStages = [
    {
      stage: t("funnel.stages.lead"),
      count: funnel.leads ?? 0,
      wowDelta: conversion_rates.l_to_v_wow_delta,
      nextConversion: conversion_rates.l_to_v,
    },
    {
      stage: t("funnel.stages.visit"),
      count: funnel.visits ?? 0,
      wowDelta: conversion_rates.v_to_o_wow_delta,
      nextConversion: conversion_rates.v_to_o,
    },
    {
      stage: t("funnel.stages.offer"),
      count: funnel.offers ?? 0,
      wowDelta: conversion_rates.l_to_o_wow_delta,
      nextConversion: conversion_rates.o_to_c,
    },
    {
      stage: t("funnel.stages.contract"),
      count: funnel.contracts ?? 0,
      wowDelta: null,
      nextConversion: null,
    },
  ];

  return (
    <>
      {/* Desktop layout: horizontal bar chart (hidden on mobile) */}
      <div className="hidden sm:block">
        <ChartContainer config={chartConfig} className="w-full h-[260px]">
          <BarChart data={chartData} barCategoryGap="30%">
            <XAxis dataKey="stage" axisLine={false} tickLine={false} />
            <YAxis hide />
            <ChartTooltip content={<ChartTooltipContent />} />
            <Bar dataKey="count" fill="var(--color-accent)" radius={[4, 4, 0, 0]}>
              <LabelList
                dataKey="count"
                position="top"
                className="fill-foreground text-xs font-semibold"
              />
            </Bar>
          </BarChart>
        </ChartContainer>
        {/* Conversion rates row */}
        <div className="grid grid-cols-4 gap-2 mt-2 px-4">
          {chartData.map((item, idx) => {
            const wow = formatWowDelta(item.wowDelta);
            return (
              <div key={item.stage} className="flex flex-col items-center gap-1">
                {idx > 0 && item.conversion && (
                  <span className="text-xs text-muted-foreground">
                    {formatPct(item.conversion)} →
                  </span>
                )}
                {wow.label && (
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      wow.positive === true
                        ? "text-ok border-ok/25"
                        : wow.positive === false
                          ? "text-danger border-danger/25"
                          : "text-muted-foreground"
                    }`}
                  >
                    {wow.label}
                  </Badge>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Mobile layout: vertical stacked (block on mobile, hidden on sm+) */}
      <div className="block sm:hidden space-y-2">
        {mobileStages.map((item, idx) => {
          const wow = formatWowDelta(item.wowDelta);
          return (
            <div key={item.stage}>
              <div className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{item.stage}</span>
                  <span className="text-xl font-bold text-foreground">
                    {item.count}
                  </span>
                </div>
                {wow.label && (
                  <Badge
                    variant="outline"
                    className={`text-xs ${
                      wow.positive === true
                        ? "text-ok border-ok/25"
                        : wow.positive === false
                          ? "text-danger border-danger/25"
                          : "text-muted-foreground"
                    }`}
                  >
                    {wow.label}
                  </Badge>
                )}
              </div>
              {idx < mobileStages.length - 1 && item.nextConversion && (
                <div className="flex justify-center py-1">
                  <span className="text-xs text-muted-foreground">
                    ↓ {formatPct(item.nextConversion)}
                  </span>
                </div>
              )}
              {idx < mobileStages.length - 1 && !item.nextConversion && (
                <div className="flex justify-center py-1">
                  <span className="text-xs text-muted-foreground">↓</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </>
  );
}
