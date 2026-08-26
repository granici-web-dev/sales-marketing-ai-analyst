/**
 * Период из адресной строки.
 *
 * Хук решает, за какие даты грузятся все три дашборда аналитика. Покрытия
 * у него не было, а ошибиться он может тремя способами, и каждый видно
 * клиенту: взять умолчание вместо ссылки, которую ему прислали; принять
 * мусор из адреса за дату; вернуть новый объект на каждом проходе и увести
 * потребителя в бесконечную перерисовку.
 */
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const searchParams = { current: new URLSearchParams() };

// Общая заглушка next/navigation из vitest.setup отдаёт пустые параметры
// на любой вызов; здесь они должны меняться от теста к тесту.
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParams.current,
}));

const { useUrlDateRange } = await import("@/hooks/useUrlDateRange");
const { getDefaultDateRange } = await import("@/lib/formatters");

/** Адресная строка — второй источник, который читает хук напрямую. */
function setLocation(search: string): void {
  window.history.replaceState({}, "", `/sales${search}`);
}

beforeEach(() => {
  searchParams.current = new URLSearchParams();
  setLocation("");
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useUrlDateRange", () => {
  it("без дат в адресе берёт умолчание — последние 30 дней", () => {
    const { result } = renderHook(() => useUrlDateRange());

    expect(result.current).toEqual(getDefaultDateRange());
  });

  it("даты из адреса выигрывают у умолчания даже без useSearchParams", () => {
    // Хук читает window.location в дополнение к useSearchParams, потому что
    // тот на первом клиентском проходе бывает пустым. Здесь параметры пусты
    // намеренно: период всё равно должен прийти из адреса, иначе присланная
    // ссылка открывает не то, что в ней написано.
    setLocation("?from=2026-03-01&to=2026-03-31");

    const { result } = renderHook(() => useUrlDateRange());

    expect(result.current).toEqual({ from: "2026-03-01", to: "2026-03-31" });
  });

  it("мусор вместо даты не доезжает до запроса", () => {
    setLocation("?from=вчера&to=2026-03-31");

    const { result } = renderHook(() => useUrlDateRange());

    // Начало откатилось к умолчанию, конец из адреса сохранился:
    // испорчено одно поле, а не весь период.
    expect(result.current.from).toBe(getDefaultDateRange().from);
    expect(result.current.to).toBe("2026-03-31");
  });

  it("правка адреса подхватывается без перезагрузки", () => {
    setLocation("?from=2026-03-01&to=2026-03-31");
    const { result, rerender } = renderHook(() => useUrlDateRange());
    expect(result.current.from).toBe("2026-03-01");

    // Так это и происходит: выбор периода делает router.push, меняются
    // searchParams, а адрес обновляется тем же переходом.
    searchParams.current = new URLSearchParams("from=2026-04-01&to=2026-04-30");
    setLocation("?from=2026-04-01&to=2026-04-30");
    rerender();

    expect(result.current).toEqual({ from: "2026-04-01", to: "2026-04-30" });
  });

  it("тот же период возвращается тем же объектом", () => {
    setLocation("?from=2026-03-01&to=2026-03-31");
    searchParams.current = new URLSearchParams("from=2026-03-01&to=2026-03-31");
    const { result, rerender } = renderHook(() => useUrlDateRange());
    const first = result.current;

    // Переход в Next отдаёт НОВЫЙ снимок параметров с тем же содержимым,
    // и эффект отрабатывает заново. Именно здесь и решается, вернётся
    // прежний объект или свежий.
    searchParams.current = new URLSearchParams("from=2026-03-01&to=2026-03-31");
    rerender();
    searchParams.current = new URLSearchParams("from=2026-03-01&to=2026-03-31");
    rerender();

    // Новый объект на каждом проходе — это новая ссылка в зависимостях
    // запроса, то есть запрос на каждую перерисовку. Дашборд с тремя
    // такими крутился бы вечно.
    expect(result.current).toBe(first);
  });
});
