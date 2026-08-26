/**
 * Настройка прогона в браузере.
 *
 * Зачем он вообще нужен рядом с 1162 проверками на vitest: те живут в jsdom,
 * а jsdom не умеет потокового чтения тела ответа. Ответ бота приходит по SSE
 * и дописывается в пузырь по кусочкам — единственное место в кабинете, где
 * важно не «что вернул хук», а «дорисовалось ли на экране». Это можно
 * проверить только настоящим браузером.
 *
 * Сервер поднимается собранным, а не в режиме разработки: проверяется то,
 * что уезжает клиенту. Порт свой, чтобы не спорить с `test:routes`.
 */
import { defineConfig, devices } from "@playwright/test";

const PORT = 3312;
const STUB_ENGINE_PORT = 3313;

export default defineConfig({
  testDir: "./tests/e2e",
  // Ожидания короткие намеренно: всё, что отвечает медленнее, отвечает
  // не по-настоящему — движок и бэкенд здесь подменены.
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: process.env.CI ? "list" : "line",

  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
  },

  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],

  // Двое: кабинет и подставной движок. Движок нужен потому, что раскладку
  // рисует сервер, и она спрашивает права со своей стороны — `page.route`
  // такие запросы не перехватывает, они уходят не из браузера.
  webServer: [
    {
      command: `node tests/e2e/stub-engine.mjs`,
      url: `http://127.0.0.1:${STUB_ENGINE_PORT}/admin/api/me`,
      reuseExistingServer: !process.env.CI,
      timeout: 20_000,
      env: { STUB_ENGINE_PORT: String(STUB_ENGINE_PORT) },
    },
    {
      // Собранное приложение, не `next dev`. Сборку делает шаг до этого —
      // как и у проверки маршрутов.
      command: `node_modules/.bin/next start -p ${PORT}`,
      url: `http://127.0.0.1:${PORT}/login`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: {
        ENGINE_BASE_URL: `http://127.0.0.1:${STUB_ENGINE_PORT}`,
        // Запросы за данными перехватывает браузер; адрес нужен лишь затем,
        // чтобы rewrite в next.config собрался.
        BACKEND_URL: `http://127.0.0.1:${STUB_ENGINE_PORT}`,
      },
    },
  ],
});
