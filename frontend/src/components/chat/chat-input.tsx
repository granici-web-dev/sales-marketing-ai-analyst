"use client";

// UI-SPEC § ChatInput + Keyboard shortcuts + Touch target NON-NEGOTIABLE.
//
// Auto-growing textarea, Send button on right (bg-accent #1, min-h/w 44px).
// Keyboard: Enter sends; Shift+Enter inserts newline; Cmd/Ctrl+Enter also sends.
// Disabled while isStreaming; tooltip via title attribute (lightweight).

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { useTranslations } from "next-intl";
import { Send, Loader2 } from "lucide-react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export interface ChatInputHandle {
  insertText: (text: string) => void;
  focus: () => void;
}

interface ChatInputProps {
  /** Called when the user presses Enter / clicks Send with a non-empty value. */
  onSend: (content: string) => void;
  /** While an SSE stream is active, the Send button is disabled. */
  isStreaming: boolean;
  className?: string;
}

export const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  function ChatInput({ onSend, isStreaming, className }, ref) {
    const t = useTranslations("chat.input");
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const [value, setValue] = useState("");

    // Auto-grow.
    useEffect(() => {
      const el = textareaRef.current;
      if (!el) return;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 240)}px`;
    }, [value]);

    useImperativeHandle(
      ref,
      () => ({
        insertText: (text: string) => {
          setValue((v) => (v ? `${v} ${text}` : text));
          textareaRef.current?.focus();
        },
        focus: () => textareaRef.current?.focus(),
      }),
      [],
    );

    const handleSubmit = useCallback(() => {
      const trimmed = value.trim();
      if (!trimmed || isStreaming) return;
      onSend(trimmed);
      setValue("");
    }, [value, isStreaming, onSend]);

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
      // Enter (alone) or Cmd/Ctrl+Enter → send.
      if (e.key === "Enter" && !e.shiftKey) {
        // Cmd/Ctrl+Enter explicitly sends too.
        e.preventDefault();
        handleSubmit();
      }
    };

    const sendDisabled = isStreaming || value.trim().length === 0;

    return (
      <div
        className={cn(
          "border-t bg-background p-3 md:p-4",
          className,
        )}
      >
        <div className="flex items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("placeholder")}
            aria-label={t("ariaLabel")}
            rows={1}
            className="resize-none max-h-[240px] focus-visible:ring-ring"
            disabled={false}
          />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={sendDisabled}
            aria-label={t("sendAriaLabel")}
            title={isStreaming ? t("sendDisabledTooltip") : t("sendTooltip")}
            className={cn(
              "min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-md bg-primary text-primary-foreground shadow-sm",
              "hover:bg-primary-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              "disabled:opacity-50 disabled:pointer-events-none",
            )}
          >
            {isStreaming ? (
              <Loader2 size={18} className="motion-safe:animate-spin" aria-hidden="true" />
            ) : (
              <Send size={18} aria-hidden="true" />
            )}
          </button>
        </div>
      </div>
    );
  },
);
