"use client";

import { Card, CardContent } from "@/components/ui/card";
import { formatRON, formatWowDelta } from "@/lib/formatters";
import { useTranslations } from "next-intl";
import type { KpiCards as KpiCardsData } from "@/hooks/useSalesDashboard";

interface KpiCardsProps {
  kpiCards: KpiCardsData;
}

interface KpiCardProps {
  label: string;
  value: string | number | null;
  delta?: string | null;
  format?: "ron" | "count";
}

function KpiCard({ label, value, delta, format }: KpiCardProps) {
  const wow = formatWowDelta(delta?.toString() ?? null);
  const displayValue =
    format === "ron"
      ? formatRON(value)
      : value !== null && value !== undefined
        ? String(value)
        : "—";

  return (
    <Card>
      <CardContent className="pt-4">
        <p className="text-xs text-muted-foreground mb-1">{label}</p>
        <p className="text-3xl font-bold text-[hsl(240_10%_4%)]">
          {displayValue}
        </p>
        {wow.label && (
          <span
            className={`text-xs font-medium mt-1 block ${
              wow.positive === true
                ? "text-green-600"
                : wow.positive === false
                  ? "text-red-600"
                  : "text-muted-foreground"
            }`}
          >
            {wow.label}
          </span>
        )}
      </CardContent>
    </Card>
  );
}

export function KpiCards({ kpiCards }: KpiCardsProps) {
  const t = useTranslations("sales");

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        label={t("kpi.leads")}
        value={kpiCards.leads_total}
        delta={kpiCards.leads_total_wow_delta}
        format="count"
      />
      <KpiCard
        label={t("kpi.visits")}
        value={kpiCards.visits_count}
        format="count"
      />
      <KpiCard
        label={t("kpi.offers")}
        value={kpiCards.offers_count}
        format="count"
      />
      <KpiCard
        label={t("kpi.contracts")}
        value={kpiCards.contracts_count}
        format="count"
      />
      <KpiCard
        label={t("kpi.revenue")}
        value={kpiCards.revenue}
        delta={kpiCards.revenue_wow_delta}
        format="ron"
      />
      <KpiCard
        label={t("kpi.avgDealSize")}
        value={kpiCards.avg_deal_size}
        format="ron"
      />
    </div>
  );
}
