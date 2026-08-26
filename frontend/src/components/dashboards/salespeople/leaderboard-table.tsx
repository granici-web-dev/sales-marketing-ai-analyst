"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { Users, ChevronUp, ChevronDown } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatRON, formatPct, formatDuration } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { type SalespersonRow } from "@/hooks/useSalespeopleDashboard";

type SortField =
  | "leads_assigned"
  | "visits_conducted"
  | "offers_sent"
  | "deals_won"
  | "revenue"
  | "win_rate"
  | "avg_time_to_first_touch_minutes"
  | "data_completeness_pct";

type SortDir = "asc" | "desc";

interface SortState {
  field: SortField;
  dir: SortDir;
}

const DEFAULT_SORT: SortState = { field: "deals_won", dir: "desc" };

interface LeaderboardTableProps {
  salespeople: SalespersonRow[];
}

function getSortValue(row: SalespersonRow, field: SortField): number {
  switch (field) {
    case "leads_assigned":
      return row.leads_assigned ?? 0;
    case "visits_conducted":
      return row.visits_conducted ?? 0;
    case "offers_sent":
      return row.offers_sent ?? 0;
    case "deals_won":
      return row.deals_won ?? 0;
    case "avg_time_to_first_touch_minutes":
      return row.avg_time_to_first_touch_minutes ?? 0;
    case "revenue":
      return parseFloat(row.revenue ?? "0");
    case "win_rate":
      return parseFloat(row.win_rate ?? "0");
    case "data_completeness_pct":
      return parseFloat(row.data_completeness_pct ?? "0");
    default:
      return 0;
  }
}

export function LeaderboardTable({ salespeople }: LeaderboardTableProps) {
  const t = useTranslations("salespeople");
  const [sortState, setSortState] = useState<SortState>(DEFAULT_SORT);

  const sortedData = useMemo(() => {
    return [...salespeople].sort((a, b) => {
      const aVal = getSortValue(a, sortState.field);
      const bVal = getSortValue(b, sortState.field);
      return sortState.dir === "asc" ? aVal - bVal : bVal - aVal;
    });
  }, [salespeople, sortState]);

  function handleSort(field: SortField) {
    setSortState((prev) => {
      if (prev.field === field) {
        // cycle: asc → desc → back to default
        if (prev.dir === "asc") return { field, dir: "desc" };
        // reset to default
        return DEFAULT_SORT;
      }
      // new field: start descending
      return { field, dir: "desc" };
    });
  }

  function SortIcon({ field }: { field: SortField }) {
    if (sortState.field !== field) return null;
    return sortState.dir === "asc" ? (
      <ChevronUp size={14} className="ml-1 inline" />
    ) : (
      <ChevronDown size={14} className="ml-1 inline" />
    );
  }

  if (salespeople.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <Users size={32} className="text-muted-foreground mb-3" aria-hidden="true" />
        <p className="text-sm font-medium text-foreground">
          {t("noData")}
        </p>
        <p className="text-xs text-muted-foreground mt-1">{t("noDataDesc")}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <Table className="min-w-[800px]">
        <TableHeader>
          <TableRow>
            {/* Rank */}
            <TableHead className="sticky left-0 bg-background z-10 w-10">
              {t("table.rank")}
            </TableHead>
            {/* Name — sticky */}
            <TableHead className="sticky left-10 bg-background z-10 min-w-[140px]">
              {t("table.name")}
            </TableHead>
            {/* Leads */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("leads_assigned")}
                aria-label={`Sort by ${t("table.leads")}`}
              >
                {t("table.leads")}
                <SortIcon field="leads_assigned" />
              </button>
            </TableHead>
            {/* Visits */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("visits_conducted")}
                aria-label={`Sort by ${t("table.visits")}`}
              >
                {t("table.visits")}
                <SortIcon field="visits_conducted" />
              </button>
            </TableHead>
            {/* Offers */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("offers_sent")}
                aria-label={`Sort by ${t("table.offers")}`}
              >
                {t("table.offers")}
                <SortIcon field="offers_sent" />
              </button>
            </TableHead>
            {/* Contracts */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("deals_won")}
                aria-label={`Sort by ${t("table.contracts")}`}
              >
                {t("table.contracts")}
                <SortIcon field="deals_won" />
              </button>
            </TableHead>
            {/* Revenue */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("revenue")}
                aria-label={`Sort by ${t("table.revenue")}`}
              >
                {t("table.revenue")}
                <SortIcon field="revenue" />
              </button>
            </TableHead>
            {/* Win rate */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("win_rate")}
                aria-label={`Sort by ${t("table.winRate")}`}
              >
                {t("table.winRate")}
                <SortIcon field="win_rate" />
              </button>
            </TableHead>
            {/* Time to first touch */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("avg_time_to_first_touch_minutes")}
                aria-label={`Sort by ${t("table.ttft")}`}
              >
                {t("table.ttft")}
                <SortIcon field="avg_time_to_first_touch_minutes" />
              </button>
            </TableHead>
            {/* Data completeness */}
            <TableHead className="text-right">
              <button
                className="min-h-[44px] flex items-center justify-end w-full"
                onClick={() => handleSort("data_completeness_pct")}
                aria-label={`Sort by ${t("table.completeness")}`}
              >
                {t("table.completeness")}
                <SortIcon field="data_completeness_pct" />
              </button>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedData.map((row, index) => {
            const ttftRed =
              row.avg_time_to_first_touch_minutes !== null &&
              row.avg_time_to_first_touch_minutes > 240;
            return (
              <TableRow key={row.external_id}>
                {/* Rank */}
                <TableCell className="sticky left-0 bg-background z-10 text-muted-foreground font-medium">
                  {index + 1}
                </TableCell>
                {/* Name — sticky */}
                <TableCell className="sticky left-10 bg-background z-10 font-medium">
                  {row.name ?? "—"}
                </TableCell>
                {/* Leads */}
                <TableCell className="text-right">
                  {row.leads_assigned ?? "—"}
                </TableCell>
                {/* Visits */}
                <TableCell className="text-right">
                  {row.visits_conducted ?? "—"}
                </TableCell>
                {/* Offers */}
                <TableCell className="text-right">
                  {row.offers_sent ?? "—"}
                </TableCell>
                {/* Contracts */}
                <TableCell className="text-right">
                  {row.deals_won ?? "—"}
                </TableCell>
                {/* Revenue */}
                <TableCell className="text-right">
                  {formatRON(row.revenue)}
                </TableCell>
                {/* Win rate */}
                <TableCell className="text-right">
                  {formatPct(row.win_rate)}
                </TableCell>
                {/* Time to first touch — red when > 240 min (4h threshold, D-05/SALES-02) */}
                <TableCell
                  className={cn(
                    "text-right",
                    ttftRed && "bg-danger/10 text-danger font-medium",
                  )}
                >
                  {formatDuration(row.avg_time_to_first_touch_minutes)}
                </TableCell>
                {/* Data completeness */}
                <TableCell className="text-right">
                  {formatPct(row.data_completeness_pct)}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
