"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

type SyncState =
  | { kind: "idle" }
  | { kind: "running"; taskId: string }
  | { kind: "success"; at: number }
  | { kind: "error"; message: string }
  | { kind: "rate-limited"; retryAfterSeconds: number };

interface TriggerResponse {
  task_id: string;
  enqueued_at: string;
}

interface StatusResponse {
  task_id: string;
  state: string;
  done: boolean;
  error: string | null;
}

const POLL_INTERVAL_MS = 2000;
const POLL_TIMEOUT_MS = 90_000;

/**
 * Triggers an on-demand MEFI sync + KPI recompute, then polls the Celery
 * task state until terminal. On success: invalidates every dashboard query
 * so all pages re-fetch fresh data.
 */
export function useSyncTrigger() {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SyncState>({ kind: "idle" });

  const mutation = useMutation({
    mutationFn: async (): Promise<StatusResponse> => {
      const triggerRes = await apiClient.post("/api/v1/sync/trigger", {});
      if (triggerRes.status === 429) {
        const retryAfter = parseInt(
          triggerRes.headers.get("Retry-After") ?? "60",
          10,
        );
        setState({ kind: "rate-limited", retryAfterSeconds: retryAfter });
        throw new Error(`429:${retryAfter}`);
      }
      if (!triggerRes.ok) {
        throw new Error(`HTTP ${triggerRes.status}`);
      }
      const trigger: TriggerResponse = await triggerRes.json();
      setState({ kind: "running", taskId: trigger.task_id });

      const deadline = Date.now() + POLL_TIMEOUT_MS;
      while (Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
        const statusRes = await apiClient.get(
          `/api/v1/sync/status?task_id=${trigger.task_id}`,
        );
        if (!statusRes.ok) continue;
        const status: StatusResponse = await statusRes.json();
        if (status.done) return status;
      }
      throw new Error("Sync timed out");
    },
    onSuccess: (status) => {
      if (status.state === "SUCCESS") {
        setState({ kind: "success", at: Date.now() });
        // Wide invalidation — every dashboard query refetches fresh data.
        queryClient.invalidateQueries({ queryKey: ["sales"] });
        queryClient.invalidateQueries({ queryKey: ["salespeople"] });
        queryClient.invalidateQueries({ queryKey: ["marketing"] });
        queryClient.invalidateQueries({ queryKey: ["health", "data"] });
        // Auto-reset success badge after a few seconds.
        setTimeout(() => {
          setState((prev) => (prev.kind === "success" ? { kind: "idle" } : prev));
        }, 5000);
      } else {
        setState({
          kind: "error",
          message: status.error ?? `Sync ${status.state.toLowerCase()}`,
        });
        setTimeout(() => {
          setState((prev) => (prev.kind === "error" ? { kind: "idle" } : prev));
        }, 6000);
      }
    },
    onError: (err: Error) => {
      // Rate-limit error already set state in mutationFn; don't overwrite it.
      if (err.message.startsWith("429:")) return;
      setState({ kind: "error", message: err.message });
      setTimeout(() => {
        setState((prev) => (prev.kind === "error" ? { kind: "idle" } : prev));
      }, 6000);
    },
  });

  return {
    trigger: () => mutation.mutate(),
    state,
    isRunning: state.kind === "running" || mutation.isPending,
  };
}
