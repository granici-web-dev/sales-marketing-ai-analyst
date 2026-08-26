/**
 * Ежедневные выводы: чтение за сегодня и за выбранный день, и обновление
 * по кнопке.
 *
 * Покрытия не было. Главное здесь — обновление: оно ждало Клода десятью
 * секундами по часам, и если тот отвечал дольше, страница показывала
 * прежний текст как свежий. Теперь ждёт признака, и проверяется именно это.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const apiClient = { get: vi.fn(), post: vi.fn() };
vi.mock("@/lib/api-client", () => ({ apiClient }));

const hooks = await import("@/hooks/useInsights");

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

async function advance(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  apiClient.get.mockReset();
  apiClient.post.mockReset();
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
});

afterEach(() => {
  vi.useRealTimers();
  queryClient.clear();
});

describe("чтение выводов", () => {
  it("день без выводов — это пусто, а не поломка", async () => {
    apiClient.get.mockResolvedValue(reply(404));

    const { result } = renderHook(() => hooks.useInsightsByDate("2026-01-05"), {
      wrapper,
    });
    await advance(0);

    // Выводы делаются не за каждый день: за выходной их может не быть,
    // и красная страница ошибки здесь сказала бы неправду.
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toBeNull();
  });

  it("без выбранной даты запрос не уходит", async () => {
    renderHook(() => hooks.useInsightsByDate(null), { wrapper });
    await advance(0);

    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("сегодняшние и вчерашние выводы лежат под разными ключами", async () => {
    apiClient.get.mockImplementation((url: string) =>
      Promise.resolve(reply(200, { date: url.includes("date=") ? "2026-01-05" : "today" })),
    );

    const today = renderHook(() => hooks.useInsightsToday(), { wrapper });
    const past = renderHook(() => hooks.useInsightsByDate("2026-01-05"), { wrapper });
    await advance(0);

    // Иначе выбор даты в календаре подменял бы сегодняшнюю сводку.
    expect(today.result.current.data).toEqual({ date: "today" });
    expect(past.result.current.data).toEqual({ date: "2026-01-05" });
  });
});

describe("обновление выводов", () => {
  it("ждёт, пока задача действительно кончится, а не десять секунд", async () => {
    apiClient.post.mockResolvedValue(reply(202, { pipeline_run_id: "task-1" }));
    apiClient.get
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValueOnce(reply(200, { done: false }))
      .mockResolvedValue(reply(200, { done: true }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate(null));

    // Здесь стояло ожидание ровно десяти секунд. На этой отметке задача
    // ещё идёт — и прежний код уже объявил бы «готово» и обновил страницу
    // старым текстом.
    await advance(10_000);
    expect(invalidate).not.toHaveBeenCalled();

    await advance(4000);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["insights", "today"] });
  });

  it("обновление за выбранный день трогает только этот день", async () => {
    apiClient.post.mockResolvedValue(reply(202, { pipeline_run_id: "task-2" }));
    apiClient.get.mockResolvedValue(reply(200, { done: true }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate("2026-01-05"));
    await advance(2000);

    // Сегодняшняя сводка при этом не должна перезапрашиваться: её никто
    // не пересчитывал.
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["insights", "2026-01-05"] });
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ["insights", "today"] });
  });

  it("слишком частое обновление возвращает срок ожидания, а не ошибку", async () => {
    apiClient.post.mockResolvedValue(reply(429, {}, { "Retry-After": "45" }));

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate(null));
    await advance(0);

    // Страница показывает по нему обратный отсчёт; ошибкой это не является.
    expect(result.current.data).toEqual({
      ok: false,
      retryAfterSeconds: 45,
      date: null,
    });
  });

  it("Retry-After датой вместо секунд не ломает отсчёт", async () => {
    apiClient.post.mockResolvedValue(
      reply(429, {}, { "Retry-After": "Wed, 26 Aug 2026 21:00:00 GMT" }),
    );

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate(null));
    await advance(0);

    expect(result.current.data?.retryAfterSeconds).toBe(60);
  });

  it("не дождавшись задачи, не выдаёт прежний текст за новый", async () => {
    apiClient.post.mockResolvedValue(reply(202, { pipeline_run_id: "task-3" }));
    apiClient.get.mockResolvedValue(reply(200, { done: false }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate(null));

    await advance(92_000);

    expect(result.current.isError).toBe(true);
    expect(invalidate).not.toHaveBeenCalled();
  });

  it("один сорвавшийся опрос не отменяет всё обновление", async () => {
    apiClient.post.mockResolvedValue(reply(202, { pipeline_run_id: "task-4" }));
    apiClient.get
      .mockResolvedValueOnce(reply(502))
      .mockResolvedValue(reply(200, { done: true }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useInsightsRefresh(), { wrapper });
    act(() => result.current.mutate(null));
    await advance(2000);
    await advance(2000);

    expect(invalidate).toHaveBeenCalledWith({ queryKey: ["insights", "today"] });
  });
});
