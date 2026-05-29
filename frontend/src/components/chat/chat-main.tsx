"use client";

// UI-SPEC § ChatMain — right pane wrapper that owns useChat + renders
// ChatHeader, MessageList, SuggestedQuestions (conditional), ChatInput.
//
// D-32 SSE consumer (via useChat). D-33 optimistic UI: the user message and
// an empty assistant bubble are pushed onto local state before the SSE
// round-trip starts. D-14 title hot-swap: the conversation envelope is
// fetched via useConversation and refetched on the SSE `done` event (the
// useChat hook invalidates `["chat","conversations"]` for us).

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { ChatHeader } from "@/components/chat/chat-header";
import { ChatInput, type ChatInputHandle } from "@/components/chat/chat-input";
import { MessageBubble, type AssistantBubbleState } from "@/components/chat/message-bubble";
import { MessageList } from "@/components/chat/message-list";
import { SuggestedQuestions } from "@/components/chat/suggested-questions";
import { WelcomeCard } from "@/components/chat/welcome-card";
import {
  useConversation,
  useConversationsList,
  useCreateConversation,
} from "@/hooks/useConversations";
import { useChat } from "@/hooks/useChat";

interface ChatMainProps {
  conversationId: string | null;
  /** Mobile hamburger that opens the conversation sheet. */
  onMobileMenu?: () => void;
}

interface OptimisticMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: "pending" | "sent" | "complete" | "fallback" | "error";
}

function generateLocalId(prefix: string): string {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

export function ChatMain({ conversationId, onMobileMenu }: ChatMainProps) {
  const t = useTranslations("chat");
  const router = useRouter();
  const inputRef = useRef<ChatInputHandle>(null);

  const { data: conversation, isLoading: isConvLoading } = useConversation(
    conversationId,
  );
  const { data: conversationsList } = useConversationsList();
  const createConversation = useCreateConversation();

  // Local message buffer for optimistic UI. Hydrated from conversation.messages
  // when the envelope arrives.
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);

  useEffect(() => {
    if (conversation?.messages && conversation.messages.length > 0) {
      setMessages(
        conversation.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          status: m.role === "assistant" ? "complete" : "sent",
        })),
      );
    } else if (!conversationId) {
      setMessages([]);
    }
    // When switching to a freshly-created empty conversation, keep messages empty.
  }, [conversation, conversationId]);

  const chat = useChat({
    onDone: ({ message_id, text, hallucination_flag }) => {
      // Replace the optimistic assistant bubble with the final DB row.
      setMessages((prev) => {
        const out = [...prev];
        const last = out[out.length - 1];
        if (last && last.role === "assistant") {
          out[out.length - 1] = {
            ...last,
            id: message_id,
            content: text,
            status: hallucination_flag ? "fallback" : "complete",
          };
        }
        return out;
      });
    },
  });

  const sendMessage = async (content: string) => {
    let convId = conversationId;
    // If we don't have a conversation yet, create one first.
    if (!convId) {
      const created = await createConversation.mutateAsync({});
      convId = created.id;
      router.push(`/chat?conversation_id=${convId}`);
    }

    // Optimistic: push user + empty assistant bubble immediately.
    const userMsg: OptimisticMessage = {
      id: generateLocalId("u"),
      role: "user",
      content,
      status: "pending",
    };
    const assistantMsg: OptimisticMessage = {
      id: generateLocalId("a"),
      role: "assistant",
      content: "",
      status: "pending",
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    await chat.sendMessage(convId, content);

    // Mark user as sent (defensive — useChat handles the assistant via onDone).
    setMessages((prev) =>
      prev.map((m) => (m.id === userMsg.id ? { ...m, status: "sent" } : m)),
    );
  };

  const handleChipSelect = (q: string) => {
    inputRef.current?.insertText(q);
  };

  const hasUserMessages = messages.some((m) => m.role === "user");

  // useMemo MUST be called unconditionally before any conditional return.
  const scrollKey = useMemo(
    () => `${messages.length}-${chat.tokens.length}`,
    [messages.length, chat.tokens.length],
  );

  // No conversation selected and the user has never had any.
  if (!conversationId && (conversationsList?.length ?? 0) === 0) {
    return (
      <div className="flex flex-1 flex-col">
        <WelcomeCard onSelectQuestion={(q) => sendMessage(q)} />
        <ChatInput
          ref={inputRef}
          onSend={sendMessage}
          isStreaming={chat.isStreaming}
        />
      </div>
    );
  }

  // No conversation selected but conversations exist — minimal centered state.
  if (!conversationId) {
    return (
      <div className="flex flex-1 flex-col">
        <div className="flex flex-1 items-center justify-center px-4 py-12 text-center">
          <p className="text-sm text-[hsl(240_4%_46%)]">
            {t("selectConversation")}
          </p>
        </div>
        <SuggestedQuestions onSelect={handleChipSelect} hidden={false} />
        <ChatInput
          ref={inputRef}
          onSend={sendMessage}
          isStreaming={chat.isStreaming}
        />
      </div>
    );
  }

  // 404 — conversation not found
  if (!isConvLoading && conversationId && conversation === null) {
    return (
      <div className="flex flex-1 flex-col">
        <div className="flex flex-1 flex-col items-center justify-center gap-3 px-4 py-12 text-center">
          <p className="text-sm">{t("conversation.notFound")}</p>
          <button
            type="button"
            onClick={() => router.push("/chat")}
            className="text-sm text-[hsl(221_83%_53%)] underline min-h-[44px]"
          >
            {t("conversation.startNew")}
          </button>
        </div>
      </div>
    );
  }

  // Determine the in-progress assistant bubble's state.
  let lastAssistantState: AssistantBubbleState = "complete";
  if (chat.isStreaming) {
    if (chat.thinkingState === "verifying-numbers") {
      lastAssistantState = "regenerating";
    } else if (chat.tokens.length > 0) {
      lastAssistantState = "streaming-with-text";
    } else if (chat.toolPills.length > 0) {
      lastAssistantState = "streaming-with-tools";
    } else {
      lastAssistantState = "streaming-empty";
    }
  }

  return (
    <div className="flex flex-1 flex-col min-w-0">
      {/* Mobile menu button + header */}
      <div className="flex items-center md:hidden border-b px-2 py-1">
        <button
          type="button"
          onClick={onMobileMenu}
          aria-label={t("sidebar.openAriaLabel")}
          className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-md"
        >
          ☰
        </button>
      </div>

      <ChatHeader
        conversationId={conversationId}
        title={conversation?.title ?? null}
      />

      <MessageList scrollKey={scrollKey} className="md:max-w-3xl md:mx-auto md:w-full">
        {messages.map((m, idx) => {
          if (m.role === "user") {
            return (
              <MessageBubble
                key={m.id}
                variant="user"
                content={m.content}
                userState={m.status === "pending" ? "pending" : "sent"}
              />
            );
          }
          // Assistant — last bubble may still be streaming.
          const isLast = idx === messages.length - 1;
          if (isLast && chat.isStreaming) {
            return (
              <MessageBubble
                key={m.id}
                variant="assistant"
                content={chat.tokens}
                assistantState={lastAssistantState}
                thinkingState={chat.thinkingState ?? "thinking"}
                pills={chat.toolPills}
              />
            );
          }
          return (
            <MessageBubble
              key={m.id}
              variant="assistant"
              content={m.content}
              assistantState={
                m.status === "fallback" ? "fallback" : "complete"
              }
            />
          );
        })}
        {chat.error && (
          <div className="rounded-md border border-[hsl(0_72%_51%)] bg-[hsl(0_72%_51%)]/10 p-3 text-sm text-[hsl(0_72%_51%)]">
            {chat.error}
          </div>
        )}
      </MessageList>

      <SuggestedQuestions onSelect={handleChipSelect} hidden={hasUserMessages} />

      <ChatInput
        ref={inputRef}
        onSend={sendMessage}
        isStreaming={chat.isStreaming}
      />
    </div>
  );
}
