/**
 * Разговоры чата: список, карточка, создание и убор в архив.
 *
 * Покрытия не было. Проверяется то, из-за чего человек видит не свои данные
 * или не видит своих: раздельное хранение активных и архивных, 404 как
 * «нет такого», а не как поломка, и обновление списка после правки.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const apiClient = { get: vi.fn(), post: vi.fn(), delete: vi.fn() };
vi.mock("@/lib/api-client", () => ({ apiClient }));

const hooks = await import("@/hooks/useConversations");

function reply(status: number, body?: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as unknown as Response;
}

let queryClient: QueryClient;

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

/**
 * Дать запросу дойти до конца.
 *
 * Здесь `waitFor` уместен: таймеры настоящие. В тестах сверки с CRM они
 * подменены, и там он бы завис — см. useSyncTrigger.test.tsx.
 */
async function settle(check: () => void): Promise<void> {
  await waitFor(check);
}

beforeEach(() => {
  apiClient.get.mockReset();
  apiClient.post.mockReset();
  apiClient.delete.mockReset();
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
});

afterEach(() => {
  queryClient.clear();
});

describe("useConversationsList", () => {
  it("активные и архивные хранятся врозь", async () => {
    apiClient.get.mockImplementation((url: string) =>
      Promise.resolve(
        reply(200, url.includes("archived=true") ? [{ id: "old" }] : [{ id: "live" }]),
      ),
    );

    const active = renderHook(() => hooks.useConversationsList(), { wrapper });
    const archived = renderHook(() => hooks.useConversationsList({ archived: true }), {
      wrapper,
    });
    // Один ключ на оба списка означал бы, что открытие архива подменяет
    // активный список, и наоборот — самый заметный вид «не мои данные».
    await settle(() => {
      expect(active.result.current.data).toEqual([{ id: "live" }]);
      expect(archived.result.current.data).toEqual([{ id: "old" }]);
    });
  });

  it("отказ сервера не выдаётся за пустой список", async () => {
    apiClient.get.mockResolvedValue(reply(500));

    const { result } = renderHook(() => hooks.useConversationsList(), { wrapper });
    // Пустой список и «сервер лёг» выглядят на экране одинаково, а значат
    // разное: первое — «разговоров нет», второе — «мы не знаем».
    await settle(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});

describe("useConversation", () => {
  it("без идентификатора запрос не уходит вовсе", async () => {
    renderHook(() => hooks.useConversation(null), { wrapper });
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiClient.get).not.toHaveBeenCalled();
  });

  it("404 — это «нет такого разговора», а не поломка", async () => {
    apiClient.get.mockResolvedValue(reply(404));

    const { result } = renderHook(() => hooks.useConversation("gone"), { wrapper });
    // Удалённый разговор по старой ссылке — обычное дело, и красная
    // страница ошибки здесь была бы неправдой.
    await settle(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.isError).toBe(false);
    expect(result.current.data).toBeNull();
  });
});

describe("создание и архив", () => {
  it("новый разговор обновляет оба списка сразу", async () => {
    apiClient.post.mockResolvedValue(reply(201, { id: "new" }));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useCreateConversation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({ initial_message: "Salut" });
    });

    // Ключ без флага архива — приставка: обновятся оба списка.
    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["chat", "conversations"],
    });
  });

  it("убранный в архив пропадает из списка без перезагрузки", async () => {
    apiClient.delete.mockResolvedValue(reply(204));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useArchiveConversation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("c-1");
    });

    expect(invalidate).toHaveBeenCalledWith({
      queryKey: ["chat", "conversations"],
    });
  });

  it("неудавшийся архив не делает вид, что удался", async () => {
    apiClient.delete.mockResolvedValue(reply(403));
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => hooks.useArchiveConversation(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("c-1").catch(() => undefined);
    });

    // Иначе разговор исчезает с экрана и возвращается при следующем
    // открытии страницы — выглядит как потеря данных.
    await settle(() => expect(result.current.isError).toBe(true));
    expect(invalidate).not.toHaveBeenCalled();
  });
});
