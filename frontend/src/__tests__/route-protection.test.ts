/**
 * Защита маршрутов — половина, которую видно из исходников.
 *
 * Однажды `proxy.ts` лежал в корне проекта, тогда как приложение живёт под
 * `src/`. Next ищет этот файл рядом с `app/`, поэтому он не загружался, и
 * `/marketing`, `/sales`, `/insights`, `/settings` отдавали 200 с полным
 * содержимым вообще без печенья. Все тесты при этом оставались зелёными:
 * код, который не исполняется, не падает.
 *
 * Здесь проверяется то, что можно проверить, не поднимая приложение: каждая
 * страница кабинета действительно уводит на вход без печенья, а список
 * открытых путей не разросся. Где лежит сам файл — в `proxy-location.test.ts`,
 * отдельно, потому что та проверка не должна зависеть от его импорта.
 *
 * Чего эта проверка НЕ доказывает — что Next этот файл подхватил. Это
 * доказывается запросом к работающему приложению: `scripts/route-protection.mjs`,
 * он же `pnpm test:routes`. Обе половины нужны: файл на месте и при этом
 * не загружен — ровно то, что уже случалось.
 */

import { readdirSync, statSync } from "node:fs";
import path from "node:path";

import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { PUBLIC_PATHS, config, proxy } from "@/proxy";

const FRONTEND_ROOT = path.resolve(__dirname, "../..");
const APP_DIR = path.join(FRONTEND_ROOT, "src/app");

/** Все `page.tsx` под `src/app`, как пути файлов от корня фронтенда. */
function findPages(dir: string, found: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = path.join(dir, entry);
    if (statSync(full).isDirectory()) findPages(full, found);
    else if (entry === "page.tsx") found.push(path.relative(FRONTEND_ROOT, full));
  }
  return found;
}

/**
 * Путь файла → адрес страницы.
 *
 * Группы в скобках из адреса выпадают — это способ раздать разные раскладки
 * без разных адресов. Динамические отрезки подставляются образцом: проверяется
 * не значение, а то, что адрес такой формы закрыт.
 */
function pathnameOf(pageFile: string): string {
  const segments = pageFile
    .replace(/^src\/app/, "")
    .replace(/\/page\.tsx$/, "")
    .split("/")
    .filter((s) => s && !(s.startsWith("(") && s.endsWith(")")))
    .map((s) => (s.startsWith("[") ? "obraz" : s));
  return `/${segments.join("/")}`;
}

async function visit(pathname: string, cookie?: string) {
  const headers = cookie ? { cookie } : undefined;
  return proxy(new NextRequest(new URL(`http://localhost${pathname}`), { headers }));
}

const PAGES = findPages(APP_DIR);
const DASHBOARD_PAGES = PAGES.filter((p) => p.includes("/(dashboard)/"));
const PUBLIC_PAGES = PAGES.filter((p) => !p.includes("/(dashboard)/"));

describe("каждая страница кабинета закрыта", () => {
  it("страницы вообще нашлись — иначе перебор ниже пуст и проверяет воздух", () => {
    expect(DASHBOARD_PAGES.length).toBeGreaterThanOrEqual(10);
  });

  it.each(DASHBOARD_PAGES)("%s без печенья уводит на вход", async (pageFile) => {
    const pathname = pathnameOf(pageFile);
    const res = await visit(pathname);

    expect(res.status, `${pathname} обязан перенаправлять`).toBe(307);
    expect(new URL(res.headers.get("location")!).pathname).toBe("/login");
  });

  it.each(DASHBOARD_PAGES)("%s с печеньем пропускается", async (pageFile) => {
    const res = await visit(pathnameOf(pageFile), "aw_session=whatever");
    expect(res.headers.get("location")).toBeNull();
  });

  it("отрезок matcher'а покрывает адреса кабинета", () => {
    const matcher = new RegExp(config.matcher[0].replace(/^\//, "^/").replace(/\/$/, ""));
    for (const pageFile of DASHBOARD_PAGES) {
      expect(matcher.test(pathnameOf(pageFile)), `${pathnameOf(pageFile)} вне matcher`).toBe(true);
    }
  });
});

describe("открытое остаётся открытым", () => {
  it.each(PUBLIC_PAGES)("%s доступна без печенья", async (pageFile) => {
    const res = await visit(pathnameOf(pageFile));
    expect(res.headers.get("location")).toBeNull();
  });

  it.each([
    ["/portal/session", "выдаёт сессию — требовать её здесь значит запереть вход"],
    ["/portal/engine/admin/api/me", "мост к движку, ходит с тем же печеньем"],
    ["/api/v1/dashboards/marketing", "переписывается на бэкенд, который сам отвечает 401"],
  ])("%s открыт: %s", async (pathname) => {
    const res = await visit(pathname);
    expect(res.headers.get("location")).toBeNull();
  });

  it("открытых путей ровно три и все названы", () => {
    // Список открытых путей — единственное место, где защиту можно снять
    // молча: достаточно добавить туда отрезок, под который попадёт кабинет.
    // Тест ломается на любой правке, чтобы правка была замечена.
    expect([...PUBLIC_PATHS]).toEqual(["/login", "/portal", "/api"]);
  });
});
