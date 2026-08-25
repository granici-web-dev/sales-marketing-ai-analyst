import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiFetch } from "../api-client";

/**
 * Regression coverage for the chat auth-expiry bug: the chat streaming POST in
 * useChat.ts used raw fetch() and bypassed this 401 → refresh → retry path, so
 * a turn sent after the 15-min access token expired failed with a generic error
 * instead of transparently refreshing. useChat now routes through apiFetch; these
 * tests lock the behavior apiFetch must provide — including that the retry
 * REPLAYS the original method + body (so the chat POST body survives the retry).
 */

function setCookie(token: string) {
  document.cookie = `access_token=${token}; path=/`;
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch 401 refresh-retry (D-02)", () => {
  beforeEach(() => {
    setCookie("OLD_TOKEN");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.cookie =
      "access_token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("passes through without refreshing when the first response is ok", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(200, { ok: true }));

    const resp = await apiFetch("/api/v1/chat/conversations");

    expect(resp.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(
      fetchMock.mock.calls.every(([u]) => !String(u).includes("/auth/refresh")),
    ).toBe(true);
  });

  it("on 401, refreshes the token and retries the original request once", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(401, { detail: "Invalid or expired token" }))
      .mockResolvedValueOnce(jsonResponse(200, { access_token: "NEW_TOKEN" }))
      .mockResolvedValueOnce(jsonResponse(200, { streamed: true }));

    const resp = await apiFetch("/api/v1/chat/conversations/abc/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: "salut" }),
    });

    expect(resp.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(3);

    // Call 2 is the refresh.
    const [refreshUrl, refreshOpts] = fetchMock.mock.calls[1];
    expect(String(refreshUrl)).toContain("/api/v1/auth/refresh");
    expect((refreshOpts as RequestInit).method).toBe("POST");

    // Call 3 replays the ORIGINAL request: same url, method, and body, with the
    // refreshed bearer token. Body replay is the streaming-POST regression.
    const [retryUrl, retryOpts] = fetchMock.mock.calls[2];
    expect(String(retryUrl)).toContain(
      "/api/v1/chat/conversations/abc/messages",
    );
    expect((retryOpts as RequestInit).method).toBe("POST");
    expect((retryOpts as RequestInit).body).toBe(
      JSON.stringify({ content: "salut" }),
    );
    const retryHeaders = new Headers((retryOpts as RequestInit).headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer NEW_TOKEN");
  });

  // NB: the "refresh fails → redirect to /login" branch is intentionally not
  // unit-tested here — it assigns window.location.href, which jsdom rejects with
  // "Not implemented: navigation". That branch is unchanged stock apiFetch
  // behavior (unrelated to the chat-streaming fix) and is covered manually.
});
