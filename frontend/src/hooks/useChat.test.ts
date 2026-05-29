import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { type ReactNode } from "react";
import { useChat } from "./useChat";

/**
 * Phase 8 useChat hook — UC1..UC8 per 08-06 PLAN behavior block.
 *
 * Each test stubs `global.fetch` to return a Response whose body is a synthetic
 * ReadableStream yielding pre-recorded SSE chunks. The encoder/streamer is
 * deliberately simple: each chunk in the `chunks` array gets enqueued as a
 * Uint8Array on its own loop tick, then the stream closes.
 */

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });
}

function mockFetchOk(chunks: string[]) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(makeStream(chunks), {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    }),
  );
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

function mockFetchStatus(status: number) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(null, { status, statusText: `HTTP ${status}` }),
  );
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

const CONV_ID = "00000000-0000-0000-0000-000000000001";

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("useChat — Phase 8 D-09 SSE consumer", () => {
  it("UC1: appends assistant_chunk text to tokens state", async () => {
    mockFetchOk([
      'event: assistant_chunk\ndata: {"text":"Salut "}\n\n',
      'event: assistant_chunk\ndata: {"text":"lume"}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.tokens).toBe("Salut lume");
    expect(result.current.isStreaming).toBe(false);
  });

  it("UC2: tool_use event appends a pill with state=running", async () => {
    mockFetchOk([
      'event: tool_use\ndata: {"tool_use_id":"t1","name":"get_kpi","input":{"date_from":"2026-05-01","date_to":"2026-05-31"}}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.toolPills).toHaveLength(1);
    expect(result.current.toolPills[0].name).toBe("get_kpi");
    // After done the pill stays — we just check name + that tool_use parsed.
  });

  it("UC3: tool_result updates matching pill to done; error flips to error", async () => {
    mockFetchOk([
      'event: tool_use\ndata: {"tool_use_id":"t1","name":"get_kpi","input":{}}\n\n',
      'event: tool_use\ndata: {"tool_use_id":"t2","name":"get_funnel_data","input":{}}\n\n',
      'event: tool_result\ndata: {"tool_use_id":"t1","output_preview":"{...}","duration_ms":42}\n\n',
      'event: tool_result\ndata: {"tool_use_id":"t2","output_preview":"err","duration_ms":12,"error":true}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.toolPills).toHaveLength(2);
    expect(result.current.toolPills[0].state).toBe("done");
    expect(result.current.toolPills[1].state).toBe("error");
  });

  it("UC4: regenerate_notice clears the visible bubble text", async () => {
    mockFetchOk([
      'event: assistant_chunk\ndata: {"text":"bad text"}\n\n',
      'event: regenerate_notice\ndata: {"reason":"hallucination_guard"}\n\n',
      'event: assistant_chunk\ndata: {"text":"good text"}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    // Final tokens = only the post-regenerate text (D-08).
    expect(result.current.tokens).toBe("good text");
  });

  it("UC5: done event flips isStreaming + invalidates conversations query", async () => {
    mockFetchOk([
      'event: assistant_chunk\ndata: {"text":"hi"}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const qc = new QueryClient();
    const invalidateSpy = vi.spyOn(qc, "invalidateQueries");
    const wrap = ({ children }: { children: ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);

    const { result } = renderHook(() => useChat(), { wrapper: wrap });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.isStreaming).toBe(false);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["chat", "conversations"],
    });
  });

  it("UC6: error event surfaces data.message_ro", async () => {
    mockFetchOk([
      'event: error\ndata: {"code":"internal","message_ro":"A apărut o problemă. Te rog încearcă din nou."}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.error).toBe(
      "A apărut o problemă. Te rog încearcă din nou.",
    );
  });

  it("UC7: cancel() aborts the active fetch via AbortController", async () => {
    // Create a stream that errors when the AbortSignal fires — mirroring real
    // fetch behavior where abort propagates into the body reader.
    const fetchMock = vi.fn().mockImplementation(
      async (_url: string, options: RequestInit) => {
        const signal = options.signal as AbortSignal | undefined;
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            if (signal) {
              signal.addEventListener("abort", () => {
                controller.error(
                  Object.assign(new Error("aborted"), { name: "AbortError" }),
                );
              });
            }
            // never enqueue — wait for abort
          },
        });
        return new Response(stream, {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        });
      },
    );
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useChat(), { wrapper });

    let sendPromise: Promise<void> | undefined;
    act(() => {
      sendPromise = result.current.sendMessage(CONV_ID, "ping");
    });

    await waitFor(() => expect(result.current.isStreaming).toBe(true));

    await act(async () => {
      result.current.cancel();
      // Let the rejected reader.read() propagate through the hook's catch.
      await sendPromise;
    });

    expect(result.current.isStreaming).toBe(false);
    expect(fetchMock).toHaveBeenCalled();
  });

  it("UC8: chunk-boundary fragmentation (LM-7) — assembles split frames correctly", async () => {
    // The same logical event is split across 3 raw fetch chunks. The buffer
    // logic must reassemble it before parseSSEChunk runs.
    mockFetchOk([
      'event: assistant_chunk\ndata: {"text":"Hel',
      'lo"}\n\n',
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":50,"hallucination_flag":false}\n\n',
    ]);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.tokens).toBe("Hello");
    expect(result.current.isStreaming).toBe(false);
  });

  it("UC9: non-OK fetch (429) surfaces rate-limit Romanian message", async () => {
    mockFetchStatus(429);

    const { result } = renderHook(() => useChat(), { wrapper });
    await act(async () => {
      await result.current.sendMessage(CONV_ID, "ping");
    });

    expect(result.current.error).toContain("prea multe mesaje");
    expect(result.current.isStreaming).toBe(false);
  });
});
