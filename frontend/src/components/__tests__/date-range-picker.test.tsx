/**
 * Выбор периода: подпись на кнопке, готовые интервалы и то, что уезжает
 * в адресную строку.
 *
 * Отдельная тема здесь — часовой пояс. Дата в адресе записана строкой
 * «2026-03-01», а календарь работает объектами Date, и перевод между ними
 * оказался неверным: `new Date("2026-03-01")` — это полночь UTC, то есть
 * западнее нулевого меридиана предыдущий день. Клиент в Бухаресте этого
 * не увидит никогда, поэтому поймать это можно только подменив пояс.
 */
import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render-with-intl";

const push = vi.fn();
const searchParams = { current: new URLSearchParams() };

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), refresh: vi.fn(), back: vi.fn() }),
  useSearchParams: () => searchParams.current,
  usePathname: () => "/sales",
}));

// Сверка с CRM здесь ни при чём — у неё свои тесты.
vi.mock("@/hooks/useSyncTrigger", () => ({
  useSyncTrigger: () => ({ trigger: vi.fn(), state: { kind: "idle" }, isRunning: false }),
}));

const { DateRangePicker } = await import("@/components/date-range-picker");

const ORIGINAL_TZ = process.env.TZ;

/** Открыть выбор периода: на узком экране это лист, и он проще в отрисовке. */
function openPicker(): void {
  window.innerWidth = 500;
  const trigger = screen.getAllByRole("button")[0]!;
  act(() => {
    fireEvent.click(trigger);
  });
}

beforeEach(() => {
  push.mockReset();
  searchParams.current = new URLSearchParams("from=2026-03-01&to=2026-03-31");
  window.history.replaceState({}, "", "/sales?from=2026-03-01&to=2026-03-31");
  window.innerWidth = 500;
});

afterEach(() => {
  process.env.TZ = ORIGINAL_TZ;
});

describe("DateRangePicker", () => {
  it("подпись на кнопке — период из адреса", () => {
    renderWithIntl(<DateRangePicker />);

    expect(screen.getAllByText("01.03.2026 – 31.03.2026").length).toBeGreaterThan(0);
  });

  it("подпись не съезжает на день западнее нулевого меридиана", () => {
    // Тот же период, тот же адрес — только часовой пояс другой. До правки
    // здесь читалось «28.02.2026 – 30.03.2026»: человек видел под кнопкой
    // не то, что стоит в ссылке, которую ему прислали.
    process.env.TZ = "America/New_York";

    renderWithIntl(<DateRangePicker />);

    expect(screen.getAllByText("01.03.2026 – 31.03.2026").length).toBeGreaterThan(0);
  });

  it("готовый интервал уезжает в адрес обеими границами", () => {
    renderWithIntl(<DateRangePicker />);
    openPicker();

    act(() => {
      fireEvent.click(screen.getByText("Ultima săptămână"));
    });

    expect(push).toHaveBeenCalledTimes(1);
    const url = push.mock.calls[0]![0] as string;
    const params = new URLSearchParams(url.slice(1));

    const from = params.get("from")!;
    const to = params.get("to")!;
    expect(from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(to).toMatch(/^\d{4}-\d{2}-\d{2}$/);

    // «Последняя неделя» — семь дней включительно, а не шесть и не восемь.
    const days = Math.round(
      (Date.parse(`${to}T00:00:00Z`) - Date.parse(`${from}T00:00:00Z`)) / 86_400_000,
    );
    expect(days).toBe(6);
  });

  it("готовый интервал не теряет остальные параметры адреса", () => {
    // На странице продавцов рядом живёт выбранный человек. Потерять его
    // при смене периода значит увезти отчёт не туда.
    searchParams.current = new URLSearchParams(
      "from=2026-03-01&to=2026-03-31&salesperson=12",
    );
    renderWithIntl(<DateRangePicker />);
    openPicker();

    act(() => {
      fireEvent.click(screen.getByText("Tot anul"));
    });

    const params = new URLSearchParams((push.mock.calls[0]![0] as string).slice(1));
    expect(params.get("salesperson")).toBe("12");
  });

  it("все готовые интервалы кончаются сегодняшним днём", () => {
    renderWithIntl(<DateRangePicker />);

    for (const label of [
      "Ultima săptămână",
      "Ultima lună",
      "Ultimele 90 zile",
      "Luna curentă",
      "Tot anul",
    ]) {
      // Выбор закрывается сам после применения — открываем заново.
      openPicker();
      push.mockReset();
      act(() => {
        fireEvent.click(screen.getByText(label));
      });
      const params = new URLSearchParams((push.mock.calls[0]![0] as string).slice(1));
      // Период, кончающийся вчера, тихо прячет сегодняшние заявки.
      expect(params.get("to")).toBe(new Date().toLocaleDateString("sv-SE"));
    }
  });
});
