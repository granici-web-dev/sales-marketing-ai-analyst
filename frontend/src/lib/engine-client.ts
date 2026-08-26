"use client";

/**
 * Запросы к движку со страницы. Через мост портала, не напрямую — почему
 * именно так, написано в `app/portal/engine/[...path]/route.ts`.
 *
 * Отказ по сессии отделён от прочих намеренно: «вас разлогинило» и «не
 * сохранилось» — разные новости, и показывать их одинаково значит заставлять
 * человека гадать, что делать дальше.
 */
export class EngineUnauthorized extends Error {
  constructor() {
    super("engine session expired");
    this.name = "EngineUnauthorized";
  }
}

export class EngineRefused extends Error {
  readonly code: string | undefined;
  constructor(message: string, code?: string) {
    super(message);
    this.name = "EngineRefused";
    this.code = code;
  }
}

/**
 * Как экрану поступить с отказом движка.
 *
 * Протухшая сессия — это не сообщение, а действие: перезагрузка возвращает
 * человека на вход. Три экрана — «Аналитика», «Внешний вид», «Установка» —
 * вместо этого показывали `err.message`, а у EngineUnauthorized это наша
 * служебная строка «engine session expired». То есть румынскому директору
 * показывали английскую фразу из нашего кода и оставляли на экране, который
 * больше ничего не покажет: перезагрузки нет, данные не придут.
 *
 * Вынесено сюда, потому что вариантов ровно два и выбирать между ними
 * в каждом `catch` заново — это двенадцать мест, где можно ошибиться, и одно
 * место, где ошибку видно.
 *
 * @param err   Что поймал `catch`.
 * @param show  Как экран показывает текст: строкой, плашкой, чем угодно.
 */
export function reportEngineError(err: unknown, show: (message: string) => void): void {
  if (err instanceof EngineUnauthorized) {
    location.reload();
    return;
  }
  show(err instanceof Error ? err.message : String(err));
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`/portal/engine/${path}`, init);

  if (response.status === 401) throw new EngineUnauthorized();

  if (!response.ok) {
    // Движок отвечает на отказ понятной фразой на языке клиента и кодом.
    // Показать её дословно правильнее, чем заменить своим «что-то пошло не так».
    const body = (await response.json().catch(() => null)) as
      | { error?: string; code?: string }
      | null;
    throw new EngineRefused(body?.error ?? `HTTP ${response.status}`, body?.code);
  }

  return (await response.json()) as T;
}

export const engineApi = {
  get: <T>(path: string): Promise<T> => call<T>(path, { method: "GET" }),

  send: <T>(path: string, method: "POST" | "PATCH" | "PUT" | "DELETE", body?: unknown): Promise<T> =>
    call<T>(path, {
      method,
      ...(body === undefined
        ? {}
        : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    }),

  /** Отдельно от `send`: у формы с файлом свой content-type, и ставит его браузер. */
  upload: <T>(path: string, form: FormData): Promise<T> =>
    call<T>(path, { method: "POST", body: form }),
};
