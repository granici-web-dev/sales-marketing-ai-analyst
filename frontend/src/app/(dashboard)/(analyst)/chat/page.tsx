"use client";

// UI-SPEC § Layout / Structure (D-13 sidebar + D-32 SSE via useChat in
// chat-main.tsx + D-36 mobile NON-NEGOTIABLE carry-forward from Phase 7).
//
// Reads `?conversation_id=<uuid>` via useSearchParams; mounts a split panel
// with the conversations sidebar on the left (desktop) or a Sheet (mobile)
// and the ChatMain pane on the right. QueryClientProvider is inherited from
// the dashboard layout (Phase 7 D-08) — do NOT re-wrap.

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatMain } from "@/components/chat/chat-main";
import { ConversationsList } from "@/components/chat/conversations-list";

function ChatPageContent() {
  const searchParams = useSearchParams();
  const conversationId = searchParams.get("conversation_id");
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  return (
    <div className="flex h-[calc(100vh-56px)] -m-4 md:-m-8">
      {/* Desktop sidebar (≥768px) */}
      <ConversationsList activeId={conversationId} mode="sidebar" />

      {/* Mobile sheet (<768px), toggled by ChatMain's hamburger */}
      <ConversationsList
        activeId={conversationId}
        mode="mobile-sheet"
        open={mobileSheetOpen}
        onOpenChange={setMobileSheetOpen}
      />

      <ChatMain
        conversationId={conversationId}
        onMobileMenu={() => setMobileSheetOpen(true)}
      />
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <ChatPageContent />
    </Suspense>
  );
}
