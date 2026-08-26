/**
 * Ответ бота дорисовывается в браузере.
 *
 * ── Что здесь было раньше ──
 *
 * Заготовка с `test.skip`, написанная под вход по паролю: «пользователь
 * входит с засеянными учётными данными». Ни того, ни другого больше нет —
 * Playwright в зависимостях не значился, `pnpm test:e2e` не существовало,
 * а вход по паролю из кабинета убран: личность удостоверяет движок. То есть
 * файл описывал договор, который нельзя было ни исполнить, ни проверить,
 * и при этом читался как покрытие.
 *
 * ── Зачем этот прогон нужен ──
 *
 * Проверок на vitest в кабинете больше тысячи, и они живут в jsdom. jsdom
 * не умеет потокового чтения тела ответа, а ответ бота именно так и приходит:
 * по SSE, кусочками, каждый дописывается в пузырь. Это единственное место,
 * где важно не «что вернул хук», а «дорисовалось ли на экране» — и проверить
 * это можно только настоящим браузером.
 *
 * ── Как здесь входят ──
 *
 * Печеньем сессии, а не формой. Кабинет закрыт проверкой в `proxy.ts`,
 * и та смотрит только НАЛИЧИЕ `aw_session`: значение непрозрачно, о нём
 * знает движок, а настоящая проверка стоит на бэкенде при каждом запросе
 * за данными. Поэтому браузеру достаточно печенья, а данные подменяются
 * на границе сети.
 *
 * Движка и бэкенда здесь нет намеренно. С ними это был бы прогон всей
 * установки — с базой, очередью и настоящими деньгами за обращение
 * к модели на каждый запуск, — и он проверял бы уже не отрисовку.
 */
import { expect, test, type Page } from "@playwright/test";

const SESSION_COOKIE = "aw_session";
const CONVERSATION_ID = "11111111-2222-3333-4444-555555555555";

/** Кадр SSE ровно в том виде, в каком его шлёт бэкенд. */
const frame = (event: string, data: unknown): string =>
  `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

/**
 * Ответ, приходящий двумя кусками.
 *
 * Двумя, а не одним: цельный ответ прошёл бы и при сломанной дописи —
 * первый же кусок оказался бы и последним, и разницы между «дописали»
 * и «заменили» не было бы видно.
 */
const STREAM =
  frame("conversation_meta", {
    conversation_id: CONVERSATION_ID,
    message_id_user: "m-user",
    message_id_assistant: "m-assistant",
  }) +
  frame("assistant_chunk", { text: "Vânzările au crescut " }) +
  frame("assistant_chunk", { text: "cu 12% față de luna trecută." }) +
  frame("done", {
    message_id: "m-assistant",
    total_input_tokens: 1200,
    total_output_tokens: 40,
    duration_ms: 900,
    hallucination_flag: false,
  });

/** Подменить бэкенд на границе сети. */
async function stubBackend(page: Page): Promise<void> {
  // Порядок важен: Playwright берёт ПОСЛЕДНИЙ подошедший перехват, поэтому
  // общий идёт первым, а частные — после него. Записанный последним, он
  // перехватывал и поток ответа, отдавая вместо него пустой список.
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({ status: 200, json: [] }),
  );

  await page.route("**/api/v1/chat/conversations/*/messages", (route) =>
    route.fulfill({
      status: 200,
      headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
      body: STREAM,
    }),
  );

  await page.route("**/api/v1/chat/conversations", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({
          status: 201,
          json: {
            id: CONVERSATION_ID,
            title: null,
            created_at: "2026-01-05T09:00:00Z",
            last_message_at: null,
            archived: false,
          },
        })
      : route.fulfill({ status: 200, json: [] }),
  );

}

test.beforeEach(async ({ context, page }) => {
  await context.addCookies([
    {
      name: SESSION_COOKIE,
      value: "e2e-session",
      domain: "127.0.0.1",
      path: "/",
    },
  ]);
  await stubBackend(page);
});

test("ответ бота дописывается в пузырь по кусочкам", async ({ page }) => {
  await page.goto("/chat");

  const input = page.getByLabel("Întrebare nouă");
  await expect(input).toBeVisible();

  await input.fill("Cum stăm cu vânzările luna asta?");
  await input.press("Enter");

  // Вопрос человека виден сразу, не дожидаясь ответа: иначе он думает,
  // что нажатие не сработало, и жмёт ещё раз.
  await expect(page.getByText("Cum stăm cu vânzările luna asta?")).toBeVisible();

  // Оба куска на экране и в одном пузыре — значит второй дописался
  // к первому, а не заменил его.
  await expect(
    page.getByText("Vânzările au crescut cu 12% față de luna trecută."),
  ).toBeVisible();
});

test("без печенья сессии кабинет не открывается", async ({ browser }) => {
  // Тот же браузер, но чистый: `proxy.ts` — единственное, что стоит между
  // посторонним и данными клиента, и работает он именно в этом слое,
  // а не в отрисовке.
  const clean = await browser.newContext();
  const page = await clean.newPage();
  await stubBackend(page);

  await page.goto("/chat");

  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByLabel("Întrebare nouă")).toHaveCount(0);

  await clean.close();
});
