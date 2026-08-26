"use client";

// UI-SPEC § ToolPillsRow — collapsing container for ToolPills.
//
// While streaming: expanded, wraps. After `done` event (state="complete"):
// collapsed to single line "🔧 N unelte folosite" using ICU plural via i18n.
// Click → re-expands the row.

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { ToolPill, type ToolPillProps } from "@/components/chat/tool-pill";

export interface ToolPillsRowProps {
  pills: Array<ToolPillProps & { tool_use_id: string }>;
  /**
   * "streaming" → render all pills (UI-SPEC).
   * "complete"  → collapse to summary line; click to re-expand.
   */
  state: "streaming" | "complete";
}

export function ToolPillsRow({ pills, state }: ToolPillsRowProps) {
  const t = useTranslations("chat.tools");
  // When state="complete", start collapsed. User can expand.
  const [open, setOpen] = useState(state === "streaming");

  if (pills.length === 0) return null;

  if (state === "streaming") {
    return (
      <div className="flex flex-wrap gap-2 mb-2" data-state="expanded">
        {pills.map((p) => (
          <ToolPill
            key={p.tool_use_id}
            name={p.name}
            input={p.input}
            state={p.state}
          />
        ))}
      </div>
    );
  }

  // Complete state: Collapsible summary line, click to re-expand.
  const summary =
    pills.length === 1
      ? t("collapsedSummaryOne")
      : t("collapsedSummary", { count: pills.length });

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="mb-2"
      data-state={open ? "expanded" : "collapsed"}
    >
      <CollapsibleTrigger className="text-xs text-muted-foreground hover:text-foreground transition-colors min-h-[24px]">
        {summary}
      </CollapsibleTrigger>
      <CollapsibleContent className="pt-2">
        <div className="flex flex-wrap gap-2">
          {pills.map((p) => (
            <ToolPill
              key={p.tool_use_id}
              name={p.name}
              input={p.input}
              state={p.state}
            />
          ))}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
