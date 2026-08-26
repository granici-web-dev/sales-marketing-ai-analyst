/**
 * Защита маршрутов — половина, которую видно только запросом.
 *
 * Проверки в `src/__tests__/` зовут `proxy()` напрямую и потому доказывают,
 * что функция рассуждает верно. Они не доказывают, что Next её вызывает.
 * Разница не умозрительная: файл уже лежал в корне проекта, Next его не
 * загружал, и весь кабинет отдавал 200 с полным содержимым без печенья, —
 * а функция при этом была написана правильно.
 *
 * Поэтому здесь поднимается собранное приложение и делаются настоящие
 * запросы. Список закрытых адресов читается из `src/app`, а не переписан
 * сюда руками: новая страница кабинета попадает под проверку сама.
 *
 * Запуск: `pnpm test:routes` (сборка должна быть готова — `pnpm build`).
 */

import { spawn } from "node:child_process";
import { createServer } from "node:net";
import { readdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const FRONTEND_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SESSION_COOKIE = "aw_session";

/* ── какие адреса обязаны быть закрыты ──────────────────────────────────── */

function findPages(dir, found = []) {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) findPages(full, found);
    else if (entry === "page.tsx") found.push(path.relative(FRONTEND_ROOT, full));
  }
  return found;
}

/** Путь файла → адрес. Группы в скобках выпадают, динамические отрезки — образец. */
function pathnameOf(pageFile) {
  const segments = pageFile
    .replace(/^src\/app/, "")
    .replace(/\/page\.tsx$/, "")
    .split("/")
    .filter((s) => s && !(s.startsWith("(") && s.endsWith(")")))
    .map((s) => (s.startsWith("[") ? "obraz" : s));
  return `/${segments.join("/")}`;
}

const PAGES = findPages(path.join(FRONTEND_ROOT, "src/app"));
const PROTECTED = [...new Set(PAGES.filter((p) => p.includes("/(dashboard)/")).map(pathnameOf))];

if (PROTECTED.length < 10) {
  console.error(
    `Найдено всего ${PROTECTED.length} закрытых адресов. Раньше их было больше десяти — ` +
      "проверка перестала что-либо перебирать, и это отказ, а не успех.",
  );
  process.exit(1);
}

/* ── поднять собранное приложение ───────────────────────────────────────── */

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.once("error", reject);
    srv.listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

async function waitForServer(base, deadlineMs = 60_000) {
  const until = Date.now() + deadlineMs;
  while (Date.now() < until) {
    try {
      await fetch(`${base}/login`, { redirect: "manual" });
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 250));
    }
  }
  throw new Error(`приложение не поднялось за ${deadlineMs} мс`);
}

/* ── сами проверки ──────────────────────────────────────────────────────── */

const failures = [];

function check(name, condition, detail) {
  if (condition) {
    console.log(`  ✓ ${name}`);
  } else {
    console.log(`  ✗ ${name}\n      ${detail}`);
    failures.push(name);
  }
}

async function main() {
  const port = await freePort();
  const base = `http://127.0.0.1:${port}`;

  /* Напрямую двоичный файл, а не через npx: npx порождает внука, и сигнал
     доходит только до посредника. И своей группой процессов, чтобы гасить
     всё дерево разом — иначе `next start` переживает уборку, держит трубы
     открытыми, и узел не завершается вовсе. Именно так этот скрипт и повесил
     первый прогон CI на одиннадцать минут. */
  const nextBin = path.join(FRONTEND_ROOT, "node_modules/.bin/next");
  const server = spawn(nextBin, ["start", "-p", String(port)], {
    cwd: FRONTEND_ROOT,
    detached: true,
    env: {
      ...process.env,
      // Значения-заглушки: ни один из проверяемых ответов до них не доходит —
      // закрытые адреса перенаправляются раньше, чем начинается отрисовка.
      ENGINE_BASE_URL: process.env.ENGINE_BASE_URL ?? "http://127.0.0.1:1",
      BACKEND_URL: process.env.BACKEND_URL ?? "http://127.0.0.1:1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const log = [];
  server.stdout.on("data", (d) => log.push(String(d)));
  server.stderr.on("data", (d) => log.push(String(d)));

  try {
    await waitForServer(base);

    console.log(`\nБез печенья — ${PROTECTED.length} закрытых адресов:`);
    for (const pathname of PROTECTED) {
      const res = await fetch(base + pathname, { redirect: "manual" });
      const location = res.headers.get("location");
      const target = location ? new URL(location, base).pathname : null;
      check(
        `${pathname} → /login`,
        res.status === 307 && target === "/login",
        `получено ${res.status}${target ? ` → ${target}` : " без перенаправления"}. ` +
          "Если это 200, защита не работает: страница отдана целиком без сессии.",
      );
    }

    console.log("\nС печеньем — те же адреса пропускаются:");
    for (const pathname of PROTECTED) {
      const res = await fetch(base + pathname, {
        redirect: "manual",
        headers: { cookie: `${SESSION_COOKIE}=proba` },
      });
      const target = res.headers.get("location")
        ? new URL(res.headers.get("location"), base).pathname
        : null;
      check(
        `${pathname} не уводит на вход`,
        target !== "/login",
        "перенаправление на /login при наличии печенья означает, что впустить " +
          "не удастся никого и кабинет закрыт целиком",
      );
    }

    console.log("\nОткрытое остаётся открытым:");
    const loginRes = await fetch(`${base}/login`, { redirect: "manual" });
    check(
      "/login отвечает 200",
      loginRes.status === 200,
      `получено ${loginRes.status}. 307 — петля перенаправления: страница входа ` +
        "требует сессию, которую на ней и получают. 404 — переписывание адреса " +
        "куда-то, чего нет: так однажды сделал next-intl, отправив /login на " +
        "/ro/login при том, что отрезка [locale] в приложении нет вовсе.",
    );

    const portalRes = await fetch(`${base}/portal/session`, {
      method: "POST",
      redirect: "manual",
      headers: { "content-type": "application/json" },
      body: "{}",
    });
    check(
      "/portal/session не уводит на вход",
      portalRes.status !== 307,
      `получено ${portalRes.status}: сессия выдаётся здесь, требовать её для входа сюда — петля`,
    );

    console.log("");
    if (failures.length) {
      console.error(`Провалено проверок: ${failures.length}`);
      process.exitCode = 1;
    } else {
      console.log(`Все проверки пройдены: ${PROTECTED.length * 2 + 2}.`);
    }
  } catch (err) {
    console.error(`\nОтказ: ${err.message}`);
    console.error(log.join("").slice(-2000));
    process.exitCode = 1;
  } finally {
    await shutdown(server);
  }
}

/** Погасить дерево процессов и дождаться, пока оно действительно умрёт. */
async function shutdown(server) {
  if (server.exitCode !== null || server.signalCode !== null) return;

  const died = new Promise((resolve) => server.once("exit", resolve));
  try {
    process.kill(-server.pid, "SIGTERM");
  } catch {
    server.kill("SIGTERM");
  }

  const killed = await Promise.race([
    died.then(() => true),
    new Promise((r) => setTimeout(() => r(false), 5_000)),
  ]);

  if (!killed) {
    try {
      process.kill(-server.pid, "SIGKILL");
    } catch {
      server.kill("SIGKILL");
    }
    await died;
  }
}

await main();

/* Явный выход. Трубы дочернего процесса могли остаться в очереди событий,
   а повисший узел в CI выглядит как бесконечно идущая проверка, а не как
   отказ, и съедает время до самого предела. */
process.exit(process.exitCode ?? 0);
