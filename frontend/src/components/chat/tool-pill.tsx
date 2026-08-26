"use client";

// UI-SPEC § Tool Pill Content Rules (D-10 transparency).
//
// Renders a single tool invocation as an inline pill with a per-tool lucide
// icon + tool name + 1-2 word hint derived from the tool input. States per
// UI-SPEC § States Matrix:
//   - running → icon animate-pulse, bg-secondary
//   - done    → icon static, bg-secondary text-muted-foreground
//   - error   → bg-destructive/10 text-destructive + "(eroare)" suffix

import {
  BookOpen,
  Calculator,
  Filter,
  GitCompare,
  Hourglass,
  Lightbulb,
  LineChart,
  List,
  PieChart,
  Store,
  TrendingDown,
  Users,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { useTranslations } from "next-intl";
import { dayCount, periodLabel } from "@/lib/tool-pill-hints";
import { cn } from "@/lib/utils";

const ICONS: Record<string, LucideIcon> = {
  get_kpi: Calculator,
  get_funnel_data: Filter,
  get_salesperson_performance: Users,
  get_leads: List,
  compare_periods: GitCompare,
  get_loss_reasons: TrendingDown,
  get_lead_categories_breakdown: PieChart,
  get_showroom_performance: Store,
  get_recent_insight: Lightbulb,
  explain_metric: BookOpen,
  get_stuck_leads: Hourglass,
  get_trend: LineChart,
};

export interface ToolPillProps {
  name: string;
  input: Record<string, unknown>;
  state: "running" | "done" | "error";
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function computeHint(name: string, input: Record<string, unknown>): string | null {
  switch (name) {
    case "get_kpi":
    case "get_funnel_data":
    case "get_loss_reasons":
    case "get_lead_categories_breakdown": {
      const df = asString(input.date_from);
      const dt = asString(input.date_to);
      return df && dt ? periodLabel({ date_from: df, date_to: dt }) : null;
    }
    case "get_salesperson_performance": {
      const df = asString(input.date_from);
      const dt = asString(input.date_to);
      const sp = asString(input.salesperson_first_name);
      const base = df && dt ? periodLabel({ date_from: df, date_to: dt }) : "";
      return sp ? (base ? `${base} · ${sp}` : sp) : base || null;
    }
    case "get_leads": {
      const lifecycle = asString(input.lifecycle) ?? "toți";
      const max = asNumber(input.limit) ?? 50;
      return `${lifecycle}, ${max} max`;
    }
    case "compare_periods": {
      const a = input.period_a as { date_from?: string; date_to?: string } | undefined;
      const b = input.period_b as { date_from?: string; date_to?: string } | undefined;
      if (a?.date_from && a?.date_to && b?.date_from && b?.date_to) {
        return `${periodLabel({ date_from: a.date_from, date_to: a.date_to })} vs ${periodLabel({ date_from: b.date_from, date_to: b.date_to })}`;
      }
      return null;
    }
    case "get_showroom_performance": {
      const df = asString(input.date_from);
      const dt = asString(input.date_to);
      const showroom = asString(input.showroom) ?? "toate showroom-urile";
      const base = df && dt ? periodLabel({ date_from: df, date_to: dt }) : "";
      return base ? `${showroom}, ${base}` : showroom;
    }
    case "get_recent_insight": {
      return asString(input.date) ?? "azi";
    }
    case "explain_metric": {
      const m = asString(input.metric_name);
      return m ? m.toUpperCase() : null;
    }
    case "get_stuck_leads": {
      const days = asNumber(input.days) ?? 14;
      return `${days}+ zile`;
    }
    case "get_trend": {
      const metric = asString(input.metric_name);
      const days = asNumber(input.period_days);
      if (metric && days) {
        return `${metric} · ${dayCount(
          new Date(Date.now() - days * 86400000).toISOString().slice(0, 10),
          new Date().toISOString().slice(0, 10),
        )}`;
      }
      return metric ?? null;
    }
    default:
      return null;
  }
}

export function ToolPill({ name, input, state }: ToolPillProps) {
  const Icon = ICONS[name] ?? Wrench;
  const t = useTranslations("chat.tools");
  const hint = computeHint(name, input);

  return (
    <span
      role="status"
      aria-label={t("ariaLabel", { tool_name: name })}
      data-state={state}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs",
        state === "error"
          ? "bg-danger/10 text-danger"
          : "bg-muted text-foreground",
        state === "done" && "text-muted-foreground",
      )}
    >
      <Icon
        size={14}
        aria-hidden="true"
        className={cn(state === "running" && "motion-safe:animate-pulse")}
      />
      <span className="font-mono">{name}</span>
      {hint && (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground">{hint}</span>
        </>
      )}
      {state === "error" && (
        <span className="ml-1 italic">{t("errorSuffix")}</span>
      )}
    </span>
  );
}
