/**
 * Кнопка «Обновить данные»: запуск сверки с CRM и ожидание задачи.
 *
 * Покрытия не было. Проверяется не «вызвался ли fetch», а четыре состояния,
 * которые видит человек — идёт, готово, отказ, слишком часто — и то, что
 * из каждого есть выход обратно в покой.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const apiClient = { get: vi.fn(), post: vi.fn() };
vi.mock("@/lib/api-client", () => ({ apiClient }));

const { useSyncTrigger } = await import("@/hooks/useSyncTrigger");

/** Ответ ровно в той части, которую читает хук. */
function reply(
  status: number,
  body?: unknown,
  headers: Record<string, string> = {},
): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name: string) => headers[name] ?? null },
    json: async () => body,
  } as unknown as Response;
}

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  vi.useFakeTimers();
  apiClient.get.mockReset();
  apiClient.post.mockReset();
  queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
});

afterEach(() => {
  vi.useRealTimers();
});

/**
 * Прокрутить время и дать промисам догнать его.
 *
 * Вместо `waitFor`: он ждёт настоящими таймерами, а здесь они подменены,
 * и ожидание не кончилось бы никогда — первая версия этих тестов именно
 * так и висла по пять секунд каждая. `advanceTimersByTimeAsync` двигает
 * часы и по дороге вычерпывает очередь микрозадач.
 */
async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

/** Запустить сверку и дать мутации стартовать. */
async function start(trigger: () => void): Promise<void> {
  act(() => trigger());
  await advance(0);
}

describe("useSyncTrigger", () => {
  it("доводит задачу до конца и обновляет все дашборды", async () => {
    apiClient.post.mockResolvedValue(reply(202, { task_id: "t-1", enqueued_at: "now" }));
    apiClient.get
      .mockResolvedValueOnce(reply(200, { task_id: "t-1", state: "STARTED", done: false, error: null }))
      .mockResolvedValueOnce(reply(200, { task_id: "t-1", state: "SUCCESS", done: true, error: null }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);

    expect(result.current.state).toEqual({ kind: "running", taskId: "t-1" });

    await advance(2000);
    await advance(2000);
    expect(result.current.state.kind).toBe("success");

    // Свежие цифры нужны всем трём дашбордам и полосе актуальности:
    // обновить один — оставить человека сравнивать старое с новым.
    const keys = invalidate.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toEqual([
      JSON.stringify(["sales"]),
      JSON.stringify(["salespeople"]),
      JSON.stringify(["marketing"]),
      JSON.stringify(["health", "data"]),
    ]);
  });

  it("отметка «готово» гаснет сама", async () => {
    apiClient.post.mockResolvedValue(reply(202, { task_id: "t-2", enqueued_at: "now" }));
    apiClient.get.mockResolvedValue(
      reply(200, { task_id: "t-2", state: "SUCCESS", done: true, error: null }),
    );

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);
    await advance(2000);
    expect(result.current.state.kind).toBe("success");

    await advance(5000);

    // Иначе галочка висит до конца дня и означает уже неизвестно что.
    expect(result.current.state).toEqual({ kind: "idle" });
  });

  it("слишком частый запуск не блокирует кнопку навсегда", async () => {
    apiClient.post.mockResolvedValue(reply(429, {}, { "Retry-After": "30" }));

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);

    expect(result.current.state).toEqual({ kind: "rate-limited", retryAfterSeconds: 30 });

    // Ровно в этом смысл Retry-After: через эти секунды можно снова.
    // Выхода из состояния не было вовсе, а кнопка в нём заблокирована —
    // то есть до перезагрузки страницы обновить данные было нельзя.
    await advance(30_000);
    expect(result.current.state).toEqual({ kind: "idle" });
  });

  it("Retry-After датой вместо секунд не даёт «NaN»", async () => {
    // По RFC заголовок может прийти датой. Наш бэкенд шлёт число, но между
    // ним и браузером стоит посредник.
    apiClient.post.mockResolvedValue(
      reply(429, {}, { "Retry-After": "Wed, 26 Aug 2026 21:00:00 GMT" }),
    );

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);

    expect(result.current.state).toEqual({ kind: "rate-limited", retryAfterSeconds: 60 });
  });

  it("упавшая задача показывается отказом и тоже гаснет", async () => {
    apiClient.post.mockResolvedValue(reply(202, { task_id: "t-3", enqueued_at: "now" }));
    apiClient.get.mockResolvedValue(
      reply(200, { task_id: "t-3", state: "FAILURE", done: true, error: "MEFI a răspuns 503" }),
    );

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);
    await advance(2000);

    expect(result.current.state).toEqual({ kind: "error", message: "MEFI a răspuns 503" });

    await advance(6000);
    expect(result.current.state).toEqual({ kind: "idle" });
  });

  it("сорвавшийся опрос не роняет всю сверку", async () => {
    apiClient.post.mockResolvedValue(reply(202, { task_id: "t-4", enqueued_at: "now" }));
    apiClient.get
      .mockResolvedValueOnce(reply(502))
      .mockResolvedValueOnce(
        reply(200, { task_id: "t-4", state: "SUCCESS", done: true, error: null }),
      );

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);

    // Один 502 от посредника посреди девяноста секунд ожидания — обычное
    // дело; считать его провалом сверки значит выбросить уже сделанную работу.
    await advance(2000);
    await advance(2000);

    expect(result.current.state.kind).toBe("success");
  });

  it("задача, не кончившаяся за отведённое время, признаётся сорванной", async () => {
    apiClient.post.mockResolvedValue(reply(202, { task_id: "t-5", enqueued_at: "now" }));
    apiClient.get.mockResolvedValue(
      reply(200, { task_id: "t-5", state: "STARTED", done: false, error: null }),
    );

    const { result } = renderHook(() => useSyncTrigger(), { wrapper });
    await start(result.current.trigger);

    await advance(92_000);

    // Вечное «идёт…» хуже отказа: человек ждёт того, чего не будет.
    expect(result.current.state.kind).toBe("error");
  });
});
