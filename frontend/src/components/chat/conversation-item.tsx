"use client";

// UI-SPEC § ConversationItem — single conversation row in the sidebar.
//
// Touch target ≥ 44px (NON-NEGOTIABLE per D-17 / D-36). States: idle, hover,
// active (border-l-accent), archiving (opacity 0.5).

import Link from "next/link";
import { useTranslations } from "next-intl";
import { formatDistanceToNow } from "date-fns";
import { ro } from "date-fns/locale";
import { cn } from "@/lib/utils";

interface ConversationItemProps {
  id: string;
  title: string | null;
  lastMessageAt: string | null;
  active: boolean;
  archiving?: boolean;
  /** Mobile-only callback to close the sidebar Sheet after navigation (D-36). */
  onNavigate?: () => void;
}

function relativeLabel(iso: string | null): string {
  if (!iso) return "";
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true, locale: ro });
  } catch {
    return "";
  }
}

export function ConversationItem({
  id,
  title,
  lastMessageAt,
  active,
  archiving = false,
  onNavigate,
}: ConversationItemProps) {
  const t = useTranslations("chat");
  const displayTitle = title ?? t("conversation.defaultTitle");
  const timestamp = relativeLabel(lastMessageAt);

  return (
    <Link
      href={`/chat?conversation_id=${id}`}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex flex-col gap-0.5 rounded-md px-3 py-2 min-h-[44px] text-sm transition-colors",
        active
          ? "bg-[hsl(221_83%_53%)]/10 text-[hsl(221_83%_53%)] border-l-[3px] border-[hsl(221_83%_53%)]"
          : "text-foreground hover:bg-[hsl(240_5%_92%)]",
        archiving && "opacity-50",
      )}
    >
      <span className="truncate font-medium">{displayTitle}</span>
      {timestamp && (
        <span className="text-xs text-[hsl(240_4%_46%)]">{timestamp}</span>
      )}
    </Link>
  );
}
