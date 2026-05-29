"use client";

// UI-SPEC § ConversationsList — sidebar (260px desktop, Sheet on mobile).
//
// The new-conversation button (bg-accent #2 from the reserved-for list)
// creates a conversation, then navigates to `/chat?conversation_id=<new_id>`.
// Empty / loading / error states per States Matrix.

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ConversationItem } from "@/components/chat/conversation-item";
import {
  useConversationsList,
  useCreateConversation,
} from "@/hooks/useConversations";
import { cn } from "@/lib/utils";

interface ConversationsListProps {
  /** Currently-active conversation id (from URL); used for active highlight. */
  activeId: string | null;
  /** Render mode: "sidebar" (desktop) or "mobile-sheet" (mobile). */
  mode?: "sidebar" | "mobile-sheet";
  /** Mobile-only: visibility of the sheet. */
  open?: boolean;
  /** Mobile-only: setter for the sheet visibility. */
  onOpenChange?: (open: boolean) => void;
}

function ListBody({
  activeId,
  onNavigate,
}: {
  activeId: string | null;
  onNavigate?: () => void;
}) {
  const t = useTranslations("chat.sidebar");
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useConversationsList();
  const createConversation = useCreateConversation();

  const handleNew = async () => {
    const created = await createConversation.mutateAsync({});
    router.push(`/chat?conversation_id=${created.id}`);
    onNavigate?.();
  };

  return (
    <div className="flex h-full flex-col">
      <div className="p-3 border-b">
        <button
          type="button"
          onClick={handleNew}
          disabled={createConversation.isPending}
          className={cn(
            "w-full inline-flex items-center justify-center gap-2 rounded-md bg-[hsl(221_83%_53%)] text-white px-3 min-h-[44px] text-sm font-medium",
            "hover:bg-[hsl(221_83%_45%)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(221_83%_53%)]",
            "disabled:opacity-60 disabled:pointer-events-none",
          )}
        >
          <Plus size={16} aria-hidden="true" />
          {t("newConversation")}
        </button>
      </div>

      <nav
        aria-label={t("title")}
        className="flex-1 overflow-y-auto p-2 space-y-1"
      >
        <p className="px-3 py-1 text-xs text-[hsl(240_4%_46%)]">
          {t("recentConversations")}
        </p>

        {isLoading && (
          <div className="space-y-2 p-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-11 w-full rounded-md" />
            ))}
          </div>
        )}

        {!isLoading && isError && (
          <div className="px-3 py-4 text-center text-sm text-[hsl(0_72%_51%)]">
            <p className="mb-2">{t("error")}</p>
            <button
              type="button"
              onClick={() => refetch()}
              className="text-[hsl(221_83%_53%)] underline min-h-[44px]"
            >
              {t("retry")}
            </button>
          </div>
        )}

        {!isLoading && !isError && data && data.length === 0 && (
          <p className="px-3 py-4 text-sm text-[hsl(240_4%_46%)]">
            {t("empty")}
          </p>
        )}

        {!isLoading && !isError && data && data.length > 0 && (
          <ul className="space-y-0.5">
            {data.map((c) => (
              <li key={c.id}>
                <ConversationItem
                  id={c.id}
                  title={c.title}
                  lastMessageAt={c.last_message_at}
                  active={c.id === activeId}
                  onNavigate={onNavigate}
                />
              </li>
            ))}
          </ul>
        )}
      </nav>
    </div>
  );
}

export function ConversationsList(props: ConversationsListProps) {
  const { activeId, mode = "sidebar", open = false, onOpenChange } = props;
  const t = useTranslations("chat.sidebar");

  if (mode === "mobile-sheet") {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="left" className="w-[85vw] max-w-[320px] p-0">
          <SheetTitle className="sr-only">{t("title")}</SheetTitle>
          <ListBody
            activeId={activeId}
            onNavigate={() => onOpenChange?.(false)}
          />
        </SheetContent>
      </Sheet>
    );
  }

  // Desktop sidebar
  return (
    <aside className="hidden md:flex w-[260px] flex-shrink-0 border-r bg-[hsl(240_5%_96%)]">
      <ListBody activeId={activeId} />
    </aside>
  );
}
