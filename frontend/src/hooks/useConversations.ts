"use client";

// Phase 8 D-13 / D-14 / D-15 / D-23 — TanStack Query hooks for conversation
// CRUD against the backend chat router (08-05). All endpoints share the
// `/api/v1/chat/conversations` prefix.

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export interface ConversationListItem {
  id: string;
  title: string | null;
  created_at: string;
  last_message_at: string | null;
  archived: boolean;
}

export interface ConversationDetail extends ConversationListItem {
  // Phase 8 plan 08-05 stores history server-side; the detail envelope returns
  // the metadata for now. Full message history is streamed via SSE.
  messages?: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
  }>;
}

const STALE_TIME = 60_000; // 1 min per Phase 7 D-11 convention

export function useConversationsList(opts?: { archived?: boolean }) {
  const archived = opts?.archived ?? false;
  return useQuery<ConversationListItem[]>({
    queryKey: ["chat", "conversations", { archived }],
    queryFn: async () => {
      const res = await apiClient.get(
        `/api/v1/chat/conversations?archived=${archived}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    staleTime: STALE_TIME,
  });
}

export function useConversation(id: string | null) {
  return useQuery<ConversationDetail | null>({
    queryKey: ["chat", "conversation", id],
    queryFn: async () => {
      if (!id) return null;
      const res = await apiClient.get(`/api/v1/chat/conversations/${id}`);
      if (res.status === 404) return null;
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    },
    enabled: Boolean(id),
    staleTime: STALE_TIME,
  });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input?: { initial_message?: string }) => {
      const res = await apiClient.post(
        "/api/v1/chat/conversations",
        input ?? {},
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<ConversationDetail>;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", "conversations"] });
    },
  });
}

export function useArchiveConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await apiClient.delete(`/api/v1/chat/conversations/${id}`);
      if (!res.ok && res.status !== 204) {
        throw new Error(`HTTP ${res.status}`);
      }
      return { id };
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["chat", "conversations"] });
    },
  });
}
