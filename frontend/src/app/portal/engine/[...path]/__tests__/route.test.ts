/**
 * Мост к API движка: что он пропускает и чего не пропускает.
 *
 * Мост, принимающий произвольный путь, — это доступ ко всему, что слушает
 * движок, включая то, что клиенту не предназначено. Поэтому префикс
 * `/admin/api/` подставляется на сервере, а сегменты пути проверяются.
 * Проверка на подделанный путь стоит здесь и обязана падать, если её ослабят.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { GET, POST } from "../route";

const COOKIE = "aw_session=opaque-token";

function request(path: string, init: RequestInit = {}): Request {
  return new Request(`http://portal.test/portal/engine/${path}`, {
    headers: { cookie: COOKIE, ...((init.headers as Record<string, string>) ?? {}) },
    ...init,
  });
}

const ctx = (path: string[]) => ({ params: Promise.resolve({ path }) });

function engineReplies(status = 200, body: unknown = { ok: true }) {
  return vi.fn(async (_url: string, _init: RequestInit) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("мост /portal/engine", () => {
  beforeEach(() => {
    process.env.ENGINE_BASE_URL = "http://engine.test";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("подставляет префикс сам и пересылает сессию", async () => {
    const fetchMock = engineReplies();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request("agents"), ctx(["agents"]));

    expect(response.status).toBe(200);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("http://engine.test/admin/api/agents");
    expect((init.headers as Headers).get("cookie")).toBe(COOKIE);
  });

  it("не пускает наружу из /admin/api", async () => {
    const fetchMock = engineReplies();
    vi.stubGlobal("fetch", fetchMock);

    const response = await GET(request("x"), ctx(["..", "..", "admin.js"]));

    expect(response.status).toBe(404);
    // Важнее кода ответа: запроса не было вовсе.
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("без сессии до движка не доходит", async () => {
    const fetchMock = engineReplies();
    vi.stubGlobal("fetch", fetchMock);

    const bare = new Request("http://portal.test/portal/engine/agents");
    const response = await GET(bare, ctx(["agents"]));

    expect(response.status).toBe(401);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("отказ движка доезжает как есть, вместе с кодом", async () => {
    vi.stubGlobal("fetch", engineReplies(422, { error: "Pachet necunoscut", code: "unknown_plan" }));

    const response = await POST(
      request("subscription/checkout", { method: "POST", body: "{}" }),
      ctx(["subscription", "checkout"]),
    );

    expect(response.status).toBe(422);
    // Движок отвечает понятной фразой на языке клиента. Заменять её своим
    // «что-то пошло не так» значит выбрасывать единственное объяснение.
    await expect(response.json()).resolves.toEqual({
      error: "Pachet necunoscut",
      code: "unknown_plan",
    });
  });
});
