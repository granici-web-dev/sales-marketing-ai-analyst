/**
 * Слева стоят агенты — значит, у каждого должен быть адрес, и он должен быть
 * один.
 *
 * Отдельно проверяется аналитик. Его манифест в движке говорит прямо: продукт
 * отдельный, со своим кабинетом и своей подпиской, движком не запускается —
 * поэтому движок и отвечает про него `unavailable`. Взять этот ответ на веру
 * значило бы запереть кабинет из-за того, что о нём спросили не того. Пункт
 * пропадал бы у всех, включая тех, кто в нём сейчас работает.
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

import { HOST_AGENT, HOST_AGENT_HREF, isLocked } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";

const ENGINE_AGENTS = [
  { id: "chatbot", access: "unlocked", tier: "basic", priceFrom: 149, daysLeft: null },
  { id: "data-analyst", access: "unavailable", tier: null, priceFrom: null, daysLeft: null },
  { id: "voice-assistant", access: "locked", tier: null, priceFrom: 249, daysLeft: null },
];

function engineFetch(agentsStatus: number, meStatus = 200) {
  return vi.fn(async (url: string) => {
    const body = url.endsWith("/admin/api/agents")
      ? { agents: ENGINE_AGENTS }
      : { email: "client@davoq.md", tenant: { name: "Sofa Belle" } };
    const status = url.endsWith("/admin/api/agents") ? agentsStatus : meStatus;
    return new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    });
  });
}

describe("loadPortalNav", () => {
  beforeEach(() => {
    process.env.ENGINE_BASE_URL = "http://engine.test";
    cookieStore.value = "session-token";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("не вошли в движок — слева остаётся аналитик, а не пустое меню", async () => {
    cookieStore.value = undefined;
    vi.stubGlobal("fetch", engineFetch(200));

    const nav = await loadPortalNav();

    expect(nav.linked).toBe(false);
    expect(nav.account).toBeNull();
    expect(nav.agents.map((a) => a.id)).toEqual([HOST_AGENT]);
    // Его экраны работают на своём входе — закрывать их из-за чужой учётной
    // записи было бы наказанием ни за что.
    expect(nav.agents[0]!.href).toBe(HOST_AGENT_HREF);
    expect(isLocked(nav.agents[0]!.access)).toBe(false);
  });

  it("каждый агент получает ровно один адрес", async () => {
    vi.stubGlobal("fetch", engineFetch(200));

    const nav = await loadPortalNav();

    expect(nav.linked).toBe(true);
    expect(nav.agents.map((a) => [a.id, a.href])).toEqual([
      ["chatbot", "/agents/chatbot"],
      // Не /agents/data-analyst: его экраны здесь, а не в движке.
      ["data-analyst", HOST_AGENT_HREF],
      ["voice-assistant", "/agents/voice-assistant"],
    ]);
  });

  it("аналитик открыт, что бы ни ответил про него движок", async () => {
    vi.stubGlobal("fetch", engineFetch(200));

    const nav = await loadPortalNav();
    const analyst = nav.agents.find((a) => a.id === HOST_AGENT)!;

    // Движок прислал про него unavailable — см. заголовок файла.
    expect(analyst.access).toBe("unlocked");
    expect(isLocked(analyst.access)).toBe(false);
  });

  it("запертый ведёт на свою страницу, а не в тупик", async () => {
    vi.stubGlobal("fetch", engineFetch(200));

    const nav = await loadPortalNav();
    const locked = nav.agents.find((a) => a.id === "voice-assistant")!;

    expect(isLocked(locked.access)).toBe(true);
    expect(locked.href).toBe("/agents/voice-assistant");
    // Цена нужна странице: без неё предложение включить — это предложение
    // неизвестно за сколько.
    expect(locked.priceFrom).toBe(249);
  });

  it("кто вошёл — видно внизу меню", async () => {
    vi.stubGlobal("fetch", engineFetch(200));

    const nav = await loadPortalNav();

    expect(nav.account).toEqual({ email: "client@davoq.md", tenantName: "Sofa Belle" });
  });
});
