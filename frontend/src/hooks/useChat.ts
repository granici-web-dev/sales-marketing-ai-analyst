"use client";

// Phase 8 D-32 SSE consumer hook — fetch + ReadableStream (NOT EventSource per
// LM-2). Maintains a tail buffer that's only flushed on the last `\n\n`
// boundary, mitigating LM-7 chunk-boundary fragmentation.
//
// Dispatches the 7 D-09 event types into local state:
//   conversation_meta  → captures real DB IDs (caller swaps optimistic IDs)
//   tool_use           → appends a pill in state="running"
//   tool_result        → updates matching pill to state="done"/"error"
//   assistant_chunk    → appends text into the streaming bubble
//   regenerate_notice  → clears `tokens` (D-08 — discard the visible bubble)
//   done               → flips isStreaming; invalidates ["chat","conversations"]
//                        so the AI title (D-14) hot-swaps in the sidebar.
//   error              → surfaces `data.message_ro` to the UI.

import { useCallback, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { parseSSEChunk, type SSEEvent } from "@/lib/chat/parseSSE";
import { apiFetch } from "@/lib/api-client";

export interface ToolPillState {
  tool_use_id: string;
  name: string;
  input: Record<string, unknown>;
  state: "running" | "done" | "error";
}

export interface ConversationMeta {
  conversation_id: string;
  message_id_user: string;
  message_id_assistant: string;
}

export interface UseChatOptions {
  /**
   * Called once when the backend emits `conversation_meta` (first SSE event).
   * Lets the caller swap optimistic message IDs for the real DB IDs (D-33).
   */
  onMeta?: (meta: ConversationMeta) => void;
  /**
   * Called when the backend emits `done`. Lets the caller persist the final
   * accumulated text + pills against the real DB ID and clear the streaming
   * buffer in the message list.
   */
  onDone?: (info: {
    message_id: string;
    text: string;
    pills: ToolPillState[];
    hallucination_flag: boolean;
  }) => void;
}

export interface UseChatResult {
  /**
   * Sends a user message and streams the assistant response. `conversationId`
   * MUST be a real DB id (creating a conversation is the caller's job — see
   * useCreateConversation in useConversations.ts).
   */
  sendMessage: (conversationId: string, content: string) => Promise<void>;
  cancel: () => void;
  isStreaming: boolean;
  /** Accumulated assistant text for the in-progress bubble (cleared on regenerate_notice — D-08). */
  tokens: string;
  /** Tool pills in current order (state mutates as tool_use → tool_result lands). */
  toolPills: ToolPillState[];
  /** Romanian error string surfaced by SSE `error` event (or rate-limit / network). */
  error: string | null;
  /**
   * Indicator state for the ThinkingIndicator inside the current bubble.
   *   - "thinking"           → before any chunk
   *   - "looking-up"         → while a tool is running
   *   - "verifying-numbers"  → after regenerate_notice (D-08)
   *   - null                 → not streaming
   */
  thinkingState: "thinking" | "looking-up" | "verifying-numbers" | null;
}

/**
 * Phase 8 D-32 SSE consumer + D-09 event dispatch.
 */
export function useChat(options?: UseChatOptions): UseChatResult {
  const qc = useQueryClient();
  const [isStreaming, setIsStreaming] = useState(false);
  const [tokens, setTokens] = useState("");
  const [toolPills, setToolPills] = useState<ToolPillState[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [thinkingState, setThinkingState] = useState<
    "thinking" | "looking-up" | "verifying-numbers" | null
  >(null);

  const abortRef = useRef<AbortController | null>(null);

  // Latest accumulators read by the SSE loop without triggering re-renders.
  const tokensRef = useRef("");
  const pillsRef = useRef<ToolPillState[]>([]);

  const reset = useCallback(() => {
    tokensRef.current = "";
    pillsRef.current = [];
    setTokens("");
    setToolPills([]);
    setError(null);
    setThinkingState("thinking");
  }, []);

  const sendMessage = useCallback(
    async (conversationId: string, content: string) => {
      reset();
      setIsStreaming(true);

      const ac = new AbortController();
      abortRef.current = ac;

      let resp: Response;
      try {
        // Route through apiFetch so an expired 15-min access token triggers
        // refresh-then-retry (D-02) instead of failing the turn with a generic
        // error. Body is a plain JSON string (not a consumed stream), so the
        // single retry replays safely; the SSE stream is read from resp.body
        // below. The raw fetch here previously bypassed the 401 interceptor —
        // that was the auth-expiry bug (2nd message after token expiry → 401).
        resp = await apiFetch(
          `/api/v1/chat/conversations/${conversationId}/messages`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
            signal: ac.signal,
          },
        );
      } catch (e) {
        if ((e as DOMException).name !== "AbortError") {
          setError("A apărut o problemă. Te rog încearcă din nou.");
        }
        setIsStreaming(false);
        setThinkingState(null);
        return;
      }

      if (!resp.ok || !resp.body) {
        // Map known HTTP statuses to UI-SPEC Romanian copy.
        if (resp.status === 429) {
          setError(
            "Ai trimis prea multe mesaje. Așteaptă câteva minute și încearcă din nou.",
          );
        } else if (resp.status === 409) {
          setError(
            "Așteaptă răspunsul curent înainte de a trimite alt mesaj.",
          );
        } else {
          setError("A apărut o problemă. Te rog încearcă din nou.");
        }
        setIsStreaming(false);
        setThinkingState(null);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      // LM-7 mitigation: keep a buffer of un-terminated bytes until we see
      // a `\n\n` boundary; only then split off the ready slice.
      let buffer = "";

      try {
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const lastBoundary = buffer.lastIndexOf("\n\n");
          if (lastBoundary === -1) continue;

          const ready = buffer.slice(0, lastBoundary + 2);
          buffer = buffer.slice(lastBoundary + 2);

          const events = parseSSEChunk(ready);
          for (const ev of events) {
            dispatch(ev);
          }
        }
        // Flush any remaining complete frames (rare — usually buffer is empty).
        if (buffer.includes("\n\n")) {
          for (const ev of parseSSEChunk(buffer)) dispatch(ev);
        }
      } catch (e) {
        if ((e as DOMException).name !== "AbortError") {
          setError("A apărut o problemă. Te rog încearcă din nou.");
        }
      } finally {
        setIsStreaming(false);
        setThinkingState(null);
        abortRef.current = null;
      }

      function dispatch(ev: SSEEvent) {
        switch (ev.event) {
          case "conversation_meta": {
            options?.onMeta?.(ev.data);
            break;
          }
          case "tool_use": {
            const pill: ToolPillState = {
              tool_use_id: ev.data.tool_use_id,
              name: ev.data.name,
              input: ev.data.input,
              state: "running",
            };
            pillsRef.current = [...pillsRef.current, pill];
            setToolPills(pillsRef.current);
            setThinkingState("looking-up");
            break;
          }
          case "tool_result": {
            pillsRef.current = pillsRef.current.map((p) =>
              p.tool_use_id === ev.data.tool_use_id
                ? { ...p, state: ev.data.error ? "error" : "done" }
                : p,
            );
            setToolPills(pillsRef.current);
            break;
          }
          case "assistant_chunk": {
            tokensRef.current += ev.data.text;
            setTokens(tokensRef.current);
            // First chunk after streaming starts: drop indicator.
            setThinkingState(null);
            break;
          }
          case "regenerate_notice": {
            // D-08: discard the visible bubble text + switch indicator.
            tokensRef.current = "";
            setTokens("");
            setThinkingState("verifying-numbers");
            break;
          }
          case "done": {
            // D-14: title hot-swap via TanStack Query refetch.
            qc.invalidateQueries({ queryKey: ["chat", "conversations"] });
            options?.onDone?.({
              message_id: ev.data.message_id,
              text: tokensRef.current,
              pills: pillsRef.current,
              hallucination_flag: ev.data.hallucination_flag,
            });
            break;
          }
          case "error": {
            setError(ev.data.message_ro);
            break;
          }
        }
      }
    },
    [options, qc, reset],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    sendMessage,
    cancel,
    isStreaming,
    tokens,
    toolPills,
    error,
    thinkingState,
  };
}
