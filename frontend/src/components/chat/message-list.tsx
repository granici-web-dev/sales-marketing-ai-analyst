"use client";

// UI-SPEC § MessageList (D-34 auto-scroll within 100px).
//
// `role="log" aria-live="polite" aria-atomic="false"` so SRs announce new
// completed messages (not every streaming token). Auto-scroll fires on every
// content change as long as the user is within 100px of the bottom; otherwise
// a floating "↓ Mesaje noi" button (accent #8) appears bottom-right.

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

const AUTOSCROLL_THRESHOLD_PX = 100;

interface MessageListProps {
  children: React.ReactNode;
  /** Bumping this value retriggers the auto-scroll effect (e.g. on each streaming chunk). */
  scrollKey: string | number;
  className?: string;
}

export function MessageList({
  children,
  scrollKey,
  className,
}: MessageListProps) {
  const t = useTranslations("chat.messages");
  const containerRef = useRef<HTMLDivElement>(null);
  const [showNewMessagesBtn, setShowNewMessagesBtn] = useState(false);

  // On every scrollKey change, auto-scroll if within threshold.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distance < AUTOSCROLL_THRESHOLD_PX) {
      el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
      setShowNewMessagesBtn(false);
    } else {
      setShowNewMessagesBtn(true);
    }
  }, [scrollKey]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distance < AUTOSCROLL_THRESHOLD_PX) {
      setShowNewMessagesBtn(false);
    }
  };

  const jumpToBottom = () => {
    const el = containerRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    setShowNewMessagesBtn(false);
  };

  return (
    <div className={cn("relative flex-1 min-h-0", className)}>
      <div
        ref={containerRef}
        role="log"
        aria-live="polite"
        aria-atomic="false"
        onScroll={handleScroll}
        className="absolute inset-0 overflow-y-auto px-4 md:px-6 py-4 flex flex-col gap-4"
      >
        {children}
      </div>

      {showNewMessagesBtn && (
        <button
          type="button"
          onClick={jumpToBottom}
          className="absolute bottom-4 right-4 inline-flex items-center gap-1 rounded-full bg-primary text-primary-foreground shadow-md px-3 py-2 text-sm min-h-[44px] motion-safe:animate-in motion-safe:fade-in"
          aria-label={t("newMessagesButton")}
        >
          <ChevronDown size={16} aria-hidden="true" />
          <span>{t("newMessagesButton")}</span>
        </button>
      )}
    </div>
  );
}
