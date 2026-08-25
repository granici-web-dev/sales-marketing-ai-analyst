"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ChevronDown, ChevronUp } from "lucide-react";
import { formatRON } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import type { Problem } from "@/hooks/useInsights";

/* Три степени, но цветов два. Высокая и средняя получают смысловые
   токены, низкая остаётся нейтральной: её место в списке уже говорит,
   что она низкая, а третий оттенок рядом читался бы как ещё одна
   степень тревоги. */
const SEVERITY_TONE = {
  high: "danger",
  medium: "warn",
  low: "neutral",
} as const;

interface ProblemCardProps {
  problem: Problem;
}

/**
 * Collapsible problem card with severity badge, estimated_loss_ron, and actions list.
 * Collapsed by default (D-15). INSI-04: shows problem.id as source trace label.
 */
export function ProblemCard({ problem }: ProblemCardProps) {
  const [open, setOpen] = useState(false); // collapsed by default per D-15
  const t = useTranslations("insights");

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card>
        <CardHeader className="pb-2 px-4 pt-4">
          {/* CollapsibleTrigger is the entire header row — 44px min touch target (D-24) */}
          <CollapsibleTrigger
            className={cn(
              "flex items-center justify-between w-full min-h-[44px] cursor-pointer",
              "rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            )}
          >
            <div className="flex items-center gap-2 flex-wrap text-left">
              <Badge
                variant={
                  SEVERITY_TONE[problem.severity as keyof typeof SEVERITY_TONE] ??
                  SEVERITY_TONE.low
                }
              >
                {t(`severity.${problem.severity}`)}
              </Badge>
              <span className="font-medium text-sm">{problem.title}</span>
              <span className="text-xs text-muted-foreground">
                {/* estimated_loss_ron is already a number — pass directly (Assumption A2) */}
                {formatRON(problem.estimated_loss_ron)}
              </span>
            </div>
            {open ? (
              <ChevronUp size={16} className="flex-shrink-0 text-muted-foreground" />
            ) : (
              <ChevronDown size={16} className="flex-shrink-0 text-muted-foreground" />
            )}
          </CollapsibleTrigger>
        </CardHeader>

        <CollapsibleContent>
          <CardContent className="pt-0 px-4 pb-4 space-y-3">
            {/* Description */}
            <p className="text-sm leading-relaxed text-foreground">
              {problem.description}
            </p>

            {/* Recommended actions */}
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
                {t("problem.actions")}
              </p>
              <ul className="space-y-2">
                {problem.actions.map((action) => (
                  <li key={action.order} className="text-sm">
                    <span className="font-medium">{action.description}</span>
                    {" — "}
                    <span className="text-muted-foreground">
                      {t("problem.owner")}: {action.owner},{" "}
                      {t("problem.deadline")}: {action.deadline}
                    </span>
                    <p className="text-xs text-muted-foreground italic mt-0.5">
                      {action.expected_outcome}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            {/* INSI-04: source trace — problem.id = rule_id from detected_problems */}
            <p className="text-xs text-muted-foreground border-t pt-2">
              {t("problem.source")}: <code className="font-mono">{problem.id}</code>
            </p>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
