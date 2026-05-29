"use client";

// UI-SPEC § SuggestedQuestions — chip row above the input.
//
// On click, inserts the chip text into the input (NOT auto-send, per D-17).
// Falls back to a static list when the dynamic fetch fails or returns < 5.
// Hidden when the active conversation already has user messages.

import { useTranslations } from "next-intl";
import { Skeleton } from "@/components/ui/skeleton";
import { useSuggestedQuestions } from "@/hooks/useSuggestedQuestions";

const STATIC_KEYS: ReadonlyArray<
  | "salesThisMonth"
  | "topSalesperson"
  | "stuckLeads"
  | "vsLastWeek"
  | "conversionDrop"
> = [
  "salesThisMonth",
  "topSalesperson",
  "stuckLeads",
  "vsLastWeek",
  "conversionDrop",
];

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
  /** Hide the row entirely when the conversation has user messages. */
  hidden?: boolean;
}

export function SuggestedQuestions({
  onSelect,
  hidden = false,
}: SuggestedQuestionsProps) {
  const t = useTranslations("chat.suggested");
  const tStatic = useTranslations("chat.suggested.static");
  const { data, isLoading } = useSuggestedQuestions("homepage");

  if (hidden) return null;

  // Build the final list: prefer the backend payload when present, otherwise
  // fall back to the 5 static localized strings.
  let questions: string[];
  if (Array.isArray(data) && data.length >= 5) {
    questions = data;
  } else {
    questions = STATIC_KEYS.map((k) => tStatic(k));
  }

  if (isLoading) {
    return (
      <div
        role="group"
        aria-label={t("sectionAriaLabel")}
        className="flex flex-wrap gap-2 px-4 md:px-6 py-3"
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-40 rounded-full" />
        ))}
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={t("sectionAriaLabel")}
      className="flex flex-wrap gap-2 px-4 md:px-6 py-3"
    >
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          onClick={() => onSelect(q)}
          className="min-h-[44px] rounded-full border border-[hsl(240_6%_90%)] bg-[hsl(240_5%_96%)] px-4 text-sm text-foreground transition-colors hover:border-[hsl(221_83%_53%)] hover:text-[hsl(221_83%_53%)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(221_83%_53%)]"
        >
          {q}
        </button>
      ))}
    </div>
  );
}
