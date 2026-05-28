"use client";

import { BarChart, Bar, XAxis, YAxis } from "recharts";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PieChart } from "lucide-react";
import { useTranslations } from "next-intl";
import { formatPct } from "@/lib/formatters";
import type { SourceBreakdownItem } from "@/hooks/useSalesDashboard";

interface SourceBreakdownProps {
  sourceBreakdown: SourceBreakdownItem[];
}

const chartConfig = {
  leads: {
    label: "Lead-uri",
    color: "var(--color-accent)",
  },
} satisfies ChartConfig;

export function SourceBreakdown({ sourceBreakdown }: SourceBreakdownProps) {
  const t = useTranslations("sales");

  const isEmpty =
    !sourceBreakdown ||
    sourceBreakdown.length === 0 ||
    sourceBreakdown.every((item) => !item.leads);

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <PieChart size={32} className="text-[#71717A] mb-3" aria-hidden="true" />
        <p className="text-sm font-medium text-[#71717A]">
          {t("sources.noData")}
        </p>
        <p className="text-xs text-[#71717A] mt-1 max-w-xs">
          {t("sources.noDataDesc")}
        </p>
      </div>
    );
  }

  const sorted = [...sourceBreakdown].sort(
    (a, b) => (b.leads ?? 0) - (a.leads ?? 0),
  );

  const chartData = sorted.map((item) => ({
    source: item.source,
    leads: item.leads ?? 0,
  }));

  return (
    <div className="space-y-4">
      {/* Horizontal bar chart: source on Y axis, leads on X axis */}
      <ChartContainer config={chartConfig} className="w-full h-[200px]">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ left: 8, right: 16, top: 4, bottom: 4 }}
        >
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="source"
            width={90}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: "#71717A" }}
          />
          <ChartTooltip content={<ChartTooltipContent />} />
          <Bar dataKey="leads" fill="var(--color-accent)" radius={[0, 4, 4, 0]}>
          </Bar>
        </BarChart>
      </ChartContainer>

      {/* Summary table below chart */}
      <div className="overflow-x-auto">
        <Table className="min-w-[400px]">
          <TableHeader>
            <TableRow>
              <TableHead>{t("sources.title")}</TableHead>
              <TableHead className="text-right">{t("sources.leadsColumn")}</TableHead>
              <TableHead className="text-right">{t("sources.conversionColumn")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((item) => (
              <TableRow key={item.source}>
                <TableCell className="font-medium">{item.source}</TableCell>
                <TableCell className="text-right">{item.leads ?? "—"}</TableCell>
                <TableCell className="text-right">
                  {item.conversion_rate ? formatPct(item.conversion_rate) : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
