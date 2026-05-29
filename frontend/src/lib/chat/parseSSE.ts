// Phase 8 D-09 + D-32 + LM-7: pure SSE chunk parser.
//
// The browser fetch + ReadableStream pattern (D-32 — NOT EventSource per LM-2)
// reads arbitrary-sized chunks. The caller (useChat hook) maintains a string
// buffer and slices on the LAST `\n\n` boundary so partial frames stay in the
// buffer for the next read. parseSSEChunk operates only on a *complete* slice
// (one or more `\n\n`-terminated frames) and returns the parsed event list.
//
// Each SSE frame is one or more lines:
//   event: <name>
//   data: <json>
//
// Lines starting with `:` are heartbeat comments (silently ignored).
// Malformed JSON in `data:` is silently skipped (LM-7 tolerance — a corrupted
// chunk must never crash the consumer).

/**
 * Discriminated union of the 7 SSE events emitted by the backend chat router.
 * Mirrors `backend/app/schemas/chat/sse_events.py` exactly (plan 08-04 / D-09).
 */
export type SSEEvent =
  | {
      event: "conversation_meta";
      data: {
        conversation_id: string;
        message_id_user: string;
        message_id_assistant: string;
      };
    }
  | { event: "tool_use"; data: { tool_use_id: string; name: string; input: Record<string, unknown> } }
  | {
      event: "tool_result";
      data: {
        tool_use_id: string;
        output_preview: string;
        duration_ms: number;
        error?: boolean;
      };
    }
  | { event: "assistant_chunk"; data: { text: string } }
  | { event: "regenerate_notice"; data: { reason: "hallucination_guard" } }
  | {
      event: "done";
      data: {
        message_id: string;
        total_input_tokens: number;
        total_output_tokens: number;
        duration_ms: number;
        hallucination_flag: boolean;
      };
    }
  | { event: "error"; data: { code: string; message_ro: string } };

/**
 * Parse one or more complete SSE frames into typed events. Assumes the caller
 * has already split the read buffer on the last `\n\n` boundary so `chunk`
 * never contains a trailing partial frame.
 *
 * Returns an empty array (not throws) for malformed JSON / empty frames so a
 * single corrupt event cannot crash the active streaming session.
 */
export function parseSSEChunk(chunk: string): SSEEvent[] {
  const events: SSEEvent[] = [];

  for (const frame of chunk.split("\n\n")) {
    if (!frame.trim()) continue;
    // Heartbeat comment frame (per W3C EventSource spec — lines starting with ':')
    if (frame.startsWith(":")) continue;

    let eventName = "message";
    let dataLine = "";
    for (const line of frame.split("\n")) {
      if (line.startsWith(":")) continue; // heartbeat line inside a frame
      if (line.startsWith("event: ")) {
        eventName = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        // Concatenate multi-line data per SSE spec; backend always emits one
        // data: line per frame but we still tolerate the canonical case.
        dataLine += line.slice(6);
      }
    }

    if (!dataLine) continue;

    try {
      const data = JSON.parse(dataLine);
      events.push({ event: eventName, data } as SSEEvent);
    } catch {
      // LM-7: tolerate partial / malformed JSON — never crash the consumer.
      continue;
    }
  }

  return events;
}
