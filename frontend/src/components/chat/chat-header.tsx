"use client";

// UI-SPEC § ChatHeader — conversation title + kebab menu (archive).
//
// Opens AlertDialog confirmation. On confirm → useArchiveConversation()
// mutation → navigate back to /chat (no conversation selected). Title is
// pulled from the conversation envelope; D-14 title hot-swap is via TanStack
// Query refetch on done.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { MoreVertical } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useArchiveConversation } from "@/hooks/useConversations";
import { cn } from "@/lib/utils";

interface ChatHeaderProps {
  conversationId: string | null;
  title: string | null;
}

export function ChatHeader({ conversationId, title }: ChatHeaderProps) {
  const t = useTranslations("chat");
  const router = useRouter();
  const archive = useArchiveConversation();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const displayTitle = title ?? t("conversation.defaultTitle");

  const onArchive = async () => {
    if (!conversationId) return;
    await archive.mutateAsync(conversationId);
    setConfirmOpen(false);
    router.push("/chat");
  };

  return (
    <header
      className={cn(
        "h-12 flex items-center justify-between border-b bg-background px-4",
      )}
    >
      <h2 className="text-sm font-medium truncate">{displayTitle}</h2>

      {conversationId && (
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              aria-label={t("conversation.kebabAriaLabel")}
              className="h-11 w-11 inline-flex items-center justify-center rounded-md hover:bg-muted"
            >
              <MoreVertical size={18} aria-hidden="true" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onSelect={() => setConfirmOpen(true)}>
              {t("archive.trigger")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}

      <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("archive.dialogTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("archive.dialogBody")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("archive.cancel")}</AlertDialogCancel>
            <AlertDialogAction
              className="bg-danger text-primary-foreground hover:bg-danger/90"
              onClick={onArchive}
            >
              {t("archive.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </header>
  );
}
