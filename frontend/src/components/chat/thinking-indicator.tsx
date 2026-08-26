"use client";

// UI-SPEC § States Matrix → ThinkingIndicator (D-10 + D-08 + Accessibility).
//
// Three pulsing dots (motion-safe so users with prefers-reduced-motion see
// static dots). When `state !== "thinking"`, an i18n label is shown next to
// the dots: the looking-up Romanian label or the verifying-numbers Romanian
// label (post-regenerate per D-08).

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

export type ThinkingState = "thinking" | "looking-up" | "verifying-numbers";

interface ThinkingIndicatorProps {
  state?: ThinkingState;
  className?: string;
}

const DOT_CLASS =
  "block h-2 w-2 rounded-full bg-muted-foreground motion-safe:animate-pulse";

export function ThinkingIndicator({
  state = "thinking",
  className,
}: ThinkingIndicatorProps) {
  const t = useTranslations("chat.indicators");

  const label =
    state === "looking-up"
      ? t("lookingUp")
      : state === "verifying-numbers"
        ? t("verifyingNumbers")
        : null;

  return (
    <span
      role="status"
      aria-live="polite"
      className={cn(
        "inline-flex items-center gap-2 text-xs text-muted-foreground",
        className,
      )}
      data-state={state}
    >
      <span className="inline-flex items-center gap-1" aria-hidden="true">
        <span
          className={DOT_CLASS}
          style={{ animationDelay: "0ms" }}
          data-testid="dot"
        />
        <span
          className={DOT_CLASS}
          style={{ animationDelay: "150ms" }}
          data-testid="dot"
        />
        <span
          className={DOT_CLASS}
          style={{ animationDelay: "300ms" }}
          data-testid="dot"
        />
      </span>
      {label && <span className="text-xs">{label}</span>}
    </span>
  );
}
