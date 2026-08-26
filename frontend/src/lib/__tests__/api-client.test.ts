/**
 * Что делает клиент запросов после перехода на общий вход.
 *
 * Раньше здесь проверялась цепочка «401 → обновить токен → повторить запрос».
 * Цепочки больше нет вместе с токеном: удостоверяет движок, его печенье
 * уезжает с каждым запросом само и живёт две недели.
 *
 * Осталось два обязательства, и оба стоит держать тестом. Первое: печенье
 * действительно отправляется — без `credentials` браузер его не приложит, а
 * кабинет молча покажет пустоту. Второе: 401 возвращает человека ко входу, а
 * не оставляет его перед экраном, который ничего не объясняет.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiFetch } from "../api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiFetch", () => {
  let assigned: string | null = null;

  beforeEach(() => {
    assigned = null;
    // window.location.href — не присваиваемое в jsdom; подменяем целиком.
    Object.defineProperty(window, "location", {
      configurable: true,
      value: {
        get href() {
          return "http://localhost/";
        },
        set href(value: string) {
          assigned = value;
        },
      },
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("отправляет печенье сессии", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/health/data");

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    // Без этого браузер не приложит печенье, и кабинет покажет пустоту
    // человеку, который вошёл.
    expect(init.credentials).toBe("include");
  });

  it("сохраняет метод и тело запроса", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/chat", { method: "POST", body: '{"q":1}' });

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"q":1}');
  });

  it("на 401 возвращает ко входу", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(401, { detail: "expired" })));

    const response = await apiFetch("/api/v1/dashboards/sales");

    expect(response.status).toBe(401);
    expect(assigned).toBe("/login");
  });

  it("ничего не делает, пока ответы в порядке", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/health/data");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(assigned).toBeNull();
  });
});
