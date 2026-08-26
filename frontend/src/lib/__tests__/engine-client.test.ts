/**
 * Клиент к движку: через него ходит каждый экран кабинета.
 *
 * Покрытия у него не было вовсе, а решает он две вещи, которые видит клиент:
 * отличить «вас разлогинило» от «не сохранилось», и показать отказ движка
 * его же словами, а не нашим «что-то пошло не так».
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  EngineRefused,
  EngineUnauthorized,
  engineApi,
  reportEngineError,
} from "@/lib/engine-client";

/** Ответ `fetch` ровно в той части, которую читает клиент. */
function reply(status: number, body?: unknown, ok?: boolean): Response {
  return {
    ok: ok ?? (status >= 200 && status < 300),
    status,
    json: async () => {
      if (body === undefined) throw new SyntaxError("not json");
      return body;
    },
  } as Response;
}

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("engineApi", () => {
  it("отдаёт разобранный ответ и ходит через мост портала", async () => {
    fetchMock.mockResolvedValue(reply(200, { plan: "pro" }));

    const data = await engineApi.get<{ plan: string }>("subscription");

    expect(data).toEqual({ plan: "pro" });
    // Не напрямую в движок: адрес моста — часть договора, а не деталь.
    expect(fetchMock).toHaveBeenCalledWith("/portal/engine/subscription", {
      method: "GET",
    });
  });

  it("401 — это EngineUnauthorized, а не обычный отказ", async () => {
    fetchMock.mockResolvedValue(reply(401));

    // Экраны различают их по типу: один перезагружает страницу,
    // другой показывает текст. Свести к одному — заставить человека гадать.
    await expect(engineApi.get("documents")).rejects.toBeInstanceOf(EngineUnauthorized);
  });

  it("отказ движка доходит до экрана его же словами и с кодом", async () => {
    fetchMock.mockResolvedValue(
      reply(422, { error: "Ați atins limita planului: 20 documente.", code: "plan_limit_documents" }),
    );

    const err = await engineApi.send("documents", "POST", { a: 1 }).catch((e) => e);

    expect(err).toBeInstanceOf(EngineRefused);
    expect((err as EngineRefused).message).toBe("Ați atins limita planului: 20 documente.");
    expect((err as EngineRefused).code).toBe("plan_limit_documents");
  });

  it("отказ без разбираемого тела не роняет запрос, а называет код", async () => {
    // 502 от посредника приходит страницей, а не JSON. Падение на разборе
    // здесь означало бы «TypeError» на экране вместо внятного отказа.
    fetchMock.mockResolvedValue(reply(502));

    const err = await engineApi.get("drive").catch((e) => e);

    expect(err).toBeInstanceOf(EngineRefused);
    expect((err as EngineRefused).message).toBe("HTTP 502");
    expect((err as EngineRefused).code).toBeUndefined();
  });

  it("тело запроса уходит с content-type, а запрос без тела — без него", async () => {
    fetchMock.mockResolvedValue(reply(200, {}));
    await engineApi.send("promotions/7", "POST", { state: "active" });
    expect(fetchMock.mock.calls[0]![1]).toEqual({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: "active" }),
    });

    fetchMock.mockResolvedValue(reply(200, {}));
    await engineApi.send("drive/sync", "POST");
    // Пустой POST с заголовком JSON и без тела — повод для 400 у строгого
    // разборщика, и повод для вопроса «а где тело» у нестрогого.
    expect(fetchMock.mock.calls[1]![1]).toEqual({ method: "POST" });
  });

  it("загрузка файла не ставит content-type — его ставит браузер", async () => {
    fetchMock.mockResolvedValue(reply(200, {}));
    const form = new FormData();

    await engineApi.upload("documents", form);

    const init = fetchMock.mock.calls[0]![1] as RequestInit;
    expect(init.body).toBe(form);
    // Свой content-type здесь стирает boundary, и движок получает
    // неразбираемую форму.
    expect(init.headers).toBeUndefined();
  });
});

describe("reportEngineError", () => {
  it("протухшая сессия перезагружает страницу и ничего не показывает", () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { reload } as unknown as Location);
    const show = vi.fn();

    reportEngineError(new EngineUnauthorized(), show);

    expect(reload).toHaveBeenCalledTimes(1);
    // Показать «engine session expired» румынскому директору — это показать
    // ему нашу служебную строку и оставить на мёртвом экране.
    expect(show).not.toHaveBeenCalled();
  });

  it("прочий отказ показывается текстом и страницу не трогает", () => {
    const reload = vi.fn();
    vi.stubGlobal("location", { reload } as unknown as Location);
    const show = vi.fn();

    reportEngineError(new EngineRefused("Domeniul nu este valid"), show);

    expect(show).toHaveBeenCalledWith("Domeniul nu este valid");
    expect(reload).not.toHaveBeenCalled();
  });

  it("не-ошибка тоже доходит текстом, а не роняет обработчик", () => {
    const show = vi.fn();
    reportEngineError("строка вместо ошибки", show);
    expect(show).toHaveBeenCalledWith("строка вместо ошибки");
  });
});
