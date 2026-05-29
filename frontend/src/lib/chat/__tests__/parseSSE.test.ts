import { describe, it, expect } from "vitest";
import { parseSSEChunk } from "../parseSSE";

/**
 * Phase 8 D-09 + LM-7 — SSE chunk parser contract.
 *
 * The Wave 0 contract (08-01 SUMMARY) reserved 5 todo entries; this file
 * activates them as PS1..PS5 per the 08-06 PLAN behavior block.
 */

describe("parseSSEChunk — Phase 8", () => {
  it("PS1: parses a complete single-event chunk", () => {
    const chunk = 'event: assistant_chunk\ndata: {"text":"Salut"}\n\n';
    const events = parseSSEChunk(chunk);
    expect(events).toEqual([
      { event: "assistant_chunk", data: { text: "Salut" } },
    ]);
  });

  it("PS2: skips heartbeat lines starting with ':'", () => {
    const chunk = ':\n\nevent: assistant_chunk\ndata: {"text":"x"}\n\n';
    const events = parseSSEChunk(chunk);
    // The leading `:` frame is a heartbeat — skipped.
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({
      event: "assistant_chunk",
      data: { text: "x" },
    });
  });

  it("PS3: returns all events when one chunk contains multiple frames", () => {
    const chunk =
      'event: tool_use\ndata: {"tool_use_id":"t1","name":"get_kpi","input":{}}\n\n' +
      'event: assistant_chunk\ndata: {"text":"Hello"}\n\n' +
      'event: done\ndata: {"message_id":"m1","total_input_tokens":10,"total_output_tokens":5,"duration_ms":42,"hallucination_flag":false}\n\n';
    const events = parseSSEChunk(chunk);
    expect(events).toHaveLength(3);
    expect(events[0].event).toBe("tool_use");
    expect(events[1].event).toBe("assistant_chunk");
    expect(events[2].event).toBe("done");
  });

  it("PS4: tolerates malformed JSON in a data: line (LM-7)", () => {
    const chunk =
      'event: assistant_chunk\ndata: {"text":"good"}\n\n' +
      "event: assistant_chunk\ndata: {malformed\n\n" +
      'event: assistant_chunk\ndata: {"text":"good2"}\n\n';
    const events = parseSSEChunk(chunk);
    // Two good events flank a corrupt middle frame that's silently dropped.
    expect(events).toHaveLength(2);
    expect((events[0].data as { text: string }).text).toBe("good");
    expect((events[1].data as { text: string }).text).toBe("good2");
  });

  it("PS5: skips empty frames", () => {
    const chunk =
      "\n\nevent: assistant_chunk\ndata: {\"text\":\"x\"}\n\n\n\n";
    const events = parseSSEChunk(chunk);
    // Leading + trailing empty frames are ignored.
    expect(events).toHaveLength(1);
  });
});
