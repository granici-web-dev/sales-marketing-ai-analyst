"use client";

// UI-SPEC § MessageBubble — single user or assistant message bubble.
//
// Variants per States Matrix:
//   user        → right-aligned, bg-secondary, max-w-[75%] (md) / [90%] (mobile)
//   assistant   → left-aligned, bg-background border; renders ToolPillsRow on
//                  top of MarkdownRenderer; ThinkingIndicator when empty;
//                  fallback / error border-left=destructive.

import { useTranslations } from "next-intl";
import { MarkdownRenderer } from "@/components/chat/markdown-renderer";
import { ToolPillsRow } from "@/components/chat/tool-pills-row";
import {
  ThinkingIndicator,
  type ThinkingState,
} from "@/components/chat/thinking-indicator";
import type { ToolPillState } from "@/hooks/useChat";
import { cn } from "@/lib/utils";

export type MessageBubbleVariant = "user" | "assistant";

export type AssistantBubbleState =
  | "streaming-empty"
  | "streaming-with-tools"
  | "streaming-with-text"
  | "complete"
  | "regenerating"
  | "fallback"
  | "error";

export interface MessageBubbleProps {
  variant: MessageBubbleVariant;
  content: string;
  // Optional — only meaningful for variant="user".
  userState?: "pending" | "sent";
  // Optional — assistant only.
  assistantState?: AssistantBubbleState;
  thinkingState?: ThinkingState;
  pills?: Array<ToolPillState>;
  errorMessage?: string | null;
}

export function MessageBubble({
  variant,
  content,
  userState = "sent",
  assistantState = "complete",
  thinkingState = "thinking",
  pills = [],
  errorMessage = null,
}: MessageBubbleProps) {
  const t = useTranslations("chat.messages");

  if (variant === "user") {
    return (
      <div
        role="article"
        aria-label={t("userAriaLabel")}
        className={cn(
          "self-end max-w-[90%] md:max-w-[75%] bg-muted rounded-lg px-4 py-3 text-sm",
          userState === "pending" && "opacity-70",
        )}
      >
        {content}
      </div>
    );
  }

  // Assistant variant
  const isFallback = assistantState === "fallback";
  const isError = assistantState === "error";
  const showThinking =
    assistantState === "streaming-empty" ||
    assistantState === "streaming-with-tools" ||
    assistantState === "regenerating";

  const pillsForRow = pills.map((p) => ({
    tool_use_id: p.tool_use_id,
    name: p.name,
    input: p.input,
    state: p.state,
  }));

  return (
    <div
      role="article"
      aria-label={t("assistantAriaLabel")}
      data-state={assistantState}
      className={cn(
        "self-start max-w-[90%] md:max-w-[75%] bg-background border rounded-lg px-4 py-3",
        (isFallback || isError) &&
          "border-l-4 border-l-danger text-danger",
      )}
    >
      {/* Tool pills sit above the markdown — collapsed when complete. */}
      {pills.length > 0 && (
        <ToolPillsRow
          pills={pillsForRow}
          state={assistantState === "complete" ? "complete" : "streaming"}
        />
      )}

      {/* Markdown content (only when we actually have tokens). */}
      {content && !isFallback && (
        <MarkdownRenderer content={content} />
      )}

      {/* Thinking dots when bubble is mid-stream. */}
      {showThinking && !content && (
        <ThinkingIndicator
          state={
            assistantState === "regenerating"
              ? "verifying-numbers"
              : assistantState === "streaming-with-tools"
                ? "looking-up"
                : thinkingState
          }
        />
      )}

      {/* Romanian fallback copy when guard fails twice (D-07). */}
      {isFallback && (
        <p className="text-sm italic">{t("fallback")}</p>
      )}

      {/* Error inline (stream `error` event). */}
      {isError && errorMessage && (
        <p className="text-sm">{errorMessage}</p>
      )}
    </div>
  );
}
