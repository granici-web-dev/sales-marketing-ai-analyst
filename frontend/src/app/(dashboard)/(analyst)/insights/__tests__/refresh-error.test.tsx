/**
 * Провал обновления на странице выводов.
 *
 * Страница читала только `isPending`: упавшая мутация просто гасила
 * ожидание, и человек оставался с прежним текстом, не зная, что обновление
 * не состоялось. Пока обновление практически не могло упасть, это было
 * терпимо; с переходом на ожидание признака вместо десяти секунд по часам
 * оно падает по-настоящему — и молчать об этом нельзя.
 */
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderWithIntl } from "@/test/render-with-intl";
import roMessages from "../../../../../../messages/ro.json";

class InsightRefreshTimeout extends Error {
  constructor() {
    super("Insight generation timed out");
    this.name = "InsightRefreshTimeout";
  }
}

const refresh = {
  mutate: vi.fn(),
  isPending: false,
  isError: false,
  error: null as Error | null,
  data: undefined as unknown,
};

vi.mock("@/hooks/useInsights", () => ({
  InsightRefreshTimeout,
  useInsightsToday: () => ({
    data: {
      date: "2026-01-05",
      status: "success",
      generation_failed: false,
      generated_at: "2026-01-05T06:00:00Z",
      payload: {
        summary: "Zi liniștită.",
        problems: [],
        positives: [],
        warnings: [],
        weekly_action_plan: [],
        generated_at: "2026-01-05T06:00:00Z",
      },
    },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useInsightsByDate: () => ({
    data: null,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
  useInsightsRefresh: () => refresh,
}));

const { default: InsightsPage } = await import("../page");

const M = roMessages.insights;

beforeEach(() => {
  refresh.isError = false;
  refresh.error = null;
});

describe("страница выводов — отказ обновления", () => {
  it("молчит, пока обновление не падало", () => {
    renderWithIntl(<InsightsPage />);

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("сорванная генерация объясняется своими словами", () => {
    refresh.isError = true;
    refresh.error = new InsightRefreshTimeout();

    renderWithIntl(<InsightsPage />);

    const alert = screen.getByRole("alert");
    // Не «Insight generation timed out»: это наша служебная строка,
    // по-английски, и румынскому директору она не говорит ничего.
    expect(alert).toHaveTextContent(M.refreshTimedOut);
    expect(alert.textContent).not.toContain("timed out");
  });

  it("сорванная генерация честно говорит, что текст остался прежним", () => {
    refresh.isError = true;
    refresh.error = new InsightRefreshTimeout();

    renderWithIntl(<InsightsPage />);

    // Сводка на экране остаётся — и человек должен знать, что она старая,
    // иначе прочтёт её как свежую.
    expect(screen.getByText("Zi liniștită.")).toBeInTheDocument();
    expect(M.refreshTimedOut).toContain("cel dinainte");
  });

  it("прочий отказ отличается от сорванной генерации", () => {
    refresh.isError = true;
    refresh.error = new Error("HTTP 500");

    renderWithIntl(<InsightsPage />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(M.refreshFailed);
    // Иначе человеку сообщат про полторы минуты ожидания там, где сервер
    // ответил отказом сразу.
    expect(alert).not.toHaveTextContent(M.refreshTimedOut);
  });
});
