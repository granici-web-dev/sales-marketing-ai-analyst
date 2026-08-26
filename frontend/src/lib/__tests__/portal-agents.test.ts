/**
 * Что портал показывает, когда движок отвечает — и когда не отвечает.
 *
 * Проверяется одно свойство, но важное: недоступный движок обязан быть
 * ошибкой, а не пустотой. Если сбой превращается в «агентов нет», человек
 * видит семь замков на том, за что заплатил, и никакого способа понять, что
 * произошло. Ровно этот способ ошибаться легче всего внести правкой позже,
 * поэтому он закреплён тестом.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const cookieStore = vi.hoisted(() => ({ value: undefined as string | undefined }));

vi.mock("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) =>
      name === "aw_session" && cookieStore.value !== undefined
        ? { name, value: cookieStore.value }
        : undefined,
  }),
}));

import { fetchPortalAgents } from "@/lib/portal-agents";

const AGENTS = [
  { id: "chatbot", access: "unlocked", tier: "basic", priceFrom: 149, daysLeft: null },
  { id: "data-analyst", access: "unavailable", tier: null, priceFrom: null, daysLeft: null },
];

function engineReplies(status: number, body: unknown = {}) {
  // Аргументы объявлены, хотя ответ от них не зависит: без них у мока пустая
  // сигнатура, и проверить, ЧТО мы послали движку, было бы нечем.
  return vi.fn(async (_url: string, _init: RequestInit) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("fetchPortalAgents", () => {
  beforeEach(() => {
    process.env.ENGINE_BASE_URL = "http://engine.test";
    cookieStore.value = "session-token";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("без печенья сессии не ходит в движок вовсе", async () => {
    cookieStore.value = undefined;
    const fetchMock = engineReplies(200);
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchPortalAgents();

    expect(result).toEqual({ ok: false, reason: "unauthenticated" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("401 от движка — это «не вошёл», а не сбой", async () => {
    vi.stubGlobal("fetch", engineReplies(401, { error: "unauthorized" }));

    const result = await fetchPortalAgents();

    expect(result).toEqual({ ok: false, reason: "unauthenticated" });
  });

  it("недоступный движок падает, а не отдаёт пустой список", async () => {
    vi.stubGlobal("fetch", engineReplies(503));

    await expect(fetchPortalAgents()).rejects.toThrow(/503/);
  });

  it("пересылает сессию движку и дополняет ответ ссылками на экраны", async () => {
    const fetchMock = engineReplies(200, { agents: AGENTS });
    vi.stubGlobal("fetch", fetchMock);

    const result = await fetchPortalAgents();

    expect(result.ok).toBe(true);
    if (!result.ok) return;

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://engine.test/admin/api/agents");
    expect((init.headers as Record<string, string>).cookie).toBe("aw_session=session-token");
    // Кеш здесь — это замок на оплаченном агенте: права меняются оплатой.
    expect(init.cache).toBe("no-store");

    // Ответ движка доезжает как есть: адреса разделов приделывает portal-nav.
    expect(result.data).toEqual(AGENTS);
  });

  it("незаданный адрес движка — поломка настройки, а не «нет доступа»", async () => {
    delete process.env.ENGINE_BASE_URL;
    vi.stubGlobal("fetch", engineReplies(200, { agents: [] }));

    await expect(fetchPortalAgents()).rejects.toThrow(/ENGINE_BASE_URL/);
  });
});
