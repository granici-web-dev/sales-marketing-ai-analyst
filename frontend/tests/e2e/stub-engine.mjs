/**
 * Подставной движок для прогона в браузере.
 *
 * Раскладка кабинета спрашивает движок со СТОРОНЫ СЕРВЕРА — какие агенты
 * оплачены и кто вошёл, — и `page.route` до этих запросов не достаёт:
 * они уходят из Next, а не из браузера. Без ответа раскладка падает,
 * и до чата дело не доходит вовсе.
 *
 * Отвечает ровно на два адреса, которые читает `portal-nav.server.ts`.
 * Всё остальное — 404: молчаливое «ок» на незнакомый путь спрятало бы
 * появление третьего запроса, о котором прогон должен узнать.
 */
import { createServer } from "node:http";

const PORT = Number(process.env.STUB_ENGINE_PORT ?? 3313);

const AGENTS = {
  agents: [
    {
      id: "data-analyst",
      access: "unlocked",
      tier: "pro",
      priceFrom: 149,
      daysLeft: null,
      plan: null,
      tiers: { basic: 99, pro: 149 },
    },
  ],
};

const ME = {
  email: "director@etalon.example",
  tenant: { name: "Etalon Mobilă", hiddenScreens: [] },
};

const ROUTES = new Map([
  ["/admin/api/agents", AGENTS],
  ["/admin/api/me", ME],
]);

createServer((req, res) => {
  const path = (req.url ?? "").split("?")[0];
  const body = ROUTES.get(path);

  if (body === undefined) {
    res.writeHead(404, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "not_stubbed", path }));
    return;
  }

  res.writeHead(200, { "content-type": "application/json" });
  res.end(JSON.stringify(body));
}).listen(PORT, "127.0.0.1", () => {
  console.log(`подставной движок на ${PORT}`);
});
