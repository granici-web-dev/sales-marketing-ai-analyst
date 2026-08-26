/**
 * Запросы к бэкенду аналитика.
 *
 * ── Чего здесь больше нет ──
 *
 * Не осталось ни чтения токена, ни заголовка Authorization, ни перехвата 401
 * с обновлением. Всё это обслуживало собственный вход аналитика, которого
 * больше нет: удостоверяет движок, его печенье живёт на этом же домене и
 * уезжает с каждым запросом само.
 *
 * Заодно ушла и застарелая дыра: токен лежал в печенье БЕЗ HttpOnly, потому
 * что его читал этот файл. Любой скрипт на странице, включая скрипт из
 * зависимости, читал его тоже. Печенье движка скриптам недоступно.
 *
 * Обновлять нечего: сессия живёт две недели и продлевается движком, а не нами.
 * 401 означает ровно одно — сессия кончилась, и человека надо вернуть ко входу.
 */

/** Куда возвращать, когда сессия кончилась. */
const LOGIN_PATH = "/login";

export async function apiFetch(url: string, options?: RequestInit): Promise<Response> {
  const response = await fetch(url, { ...options, credentials: "include" });

  if (response.status === 401 && typeof window !== "undefined") {
    // Возврат ко входу, а не молчаливая пустая страница: человек должен
    // понимать, что от него хотят.
    window.location.href = LOGIN_PATH;
  }

  return response;
}

export const apiClient = {
  get: (url: string) => apiFetch(url),
  post: (url: string, body: unknown) =>
    apiFetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  put: (url: string, body: unknown) =>
    apiFetch(url, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  delete: (url: string) =>
    apiFetch(url, {
      method: "DELETE",
    }),
};
