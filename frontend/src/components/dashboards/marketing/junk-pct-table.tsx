"use client";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatPct } from "@/lib/formatters";
import { useTranslations } from "next-intl";
import { PieChart } from "lucide-react";
import type { JunkBySource } from "@/hooks/useMarketingDashboard";

interface JunkPctTableProps {
  junkBySource: JunkBySource[];
}

export function JunkPctTable({ junkBySource }: JunkPctTableProps) {
  const t = useTranslations("marketing");

  if (junkBySource.length === 0) {
    return (
      <div className="flex min-h-[120px] flex-col items-center justify-center py-8 text-center">
        <PieChart
          size={32}
          className="mb-3 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-muted-foreground">
          {t("junk.title")}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">—</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[400px]">
        <TableHeader>
          <TableRow>
            <TableHead>{t("junk.source")}</TableHead>
            <TableHead className="text-right">{t("junk.junkCount")}</TableHead>
            <TableHead className="text-right">{t("junk.totalLeads")}</TableHead>
            <TableHead className="text-right">{t("junk.junkPct")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {junkBySource.map((row) => (
            <TableRow key={row.source}>
              <TableCell className="font-medium">{row.source}</TableCell>
              <TableCell className="text-right">
                {row.junk_count ?? "—"}
              </TableCell>
              <TableCell className="text-right">
                {row.total_leads ?? "—"}
              </TableCell>
              <TableCell className="text-right">
                {formatPct(row.junk_pct)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
