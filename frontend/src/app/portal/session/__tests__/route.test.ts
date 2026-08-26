/**
 * Вход в портал: что мы ставим человеку и когда отказываемся.
 *
 * Тут проверяются два свойства, и второе неочевидное.
 *
 * Первое — печенье остаётся сильным. Значение приходит от движка, но флаги
 * ставим мы, и потерять HttpOnly здесь означало бы отдать сессию движка
 * первому же скрипту на странице.
 *
 * Второе — «вошёл, но сессии нет» не считается входом. Ответ 200 без
 * set-cookie выглядит успехом, и соблазн пустить человека дальше велик; он
 * тут же получит 401 на первом запросе и будет думать, что сломался кабинет.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { POST } from "../route";

const LOGIN = { email: "client@davoq.md", password: "correct-horse" };

function request(body: unknown): Request {
  return new Request("http://portal.test/portal/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

function engineReplies(status: number, setCookie?: string) {
  const headers = new Headers({ "content-type": "application/json" });
  if (setCookie) headers.append("set-cookie", setCookie);
  return vi.fn(async () => new Response(JSON.stringify({}), { status, headers }));
}

describe("POST /portal/session", () => {
  beforeEach(() => {
    process.env.ENGINE_BASE_URL = "http://engine.test";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("неверный пароль остаётся неверным паролем", async () => {
    vi.stubGlobal("fetch", engineReplies(401));

    const response = await POST(request(LOGIN));

    expect(response.status).toBe(401);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("пустое тело не доходит до движка", async () => {
    const fetchMock = engineReplies(200, "aw_session=t; Path=/");
    vi.stubGlobal("fetch", fetchMock);

    const response = await POST(request({ email: "", password: "" }));

    expect(response.status).toBe(400);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("«вошёл», но сессии не дали — это не вход", async () => {
    vi.stubGlobal("fetch", engineReplies(200));

    const response = await POST(request(LOGIN));

    expect(response.status).toBe(502);
    expect(response.headers.get("set-cookie")).toBeNull();
  });

  it("сессию движка ставим на свой домен, не ослабляя её", async () => {
    vi.stubGlobal(
      "fetch",
      engineReplies(200, "aw_session=opaque-token; Path=/; HttpOnly; SameSite=Strict; Max-Age=1209600"),
    );

    const response = await POST(request(LOGIN));

    expect(response.status).toBe(200);
    const cookie = response.headers.get("set-cookie") ?? "";
    // Значение то же самое: своей сессии мы не заводим, отзыв в движке
    // обязан действовать немедленно.
    expect(cookie).toContain("aw_session=opaque-token");
    expect(cookie).toContain("HttpOnly");
    expect(cookie.toLowerCase()).toContain("samesite=strict");
    expect(cookie).toContain("Path=/");
  });
});
