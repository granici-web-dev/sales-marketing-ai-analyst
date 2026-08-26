/**
 * Где лежит `proxy.ts`.
 *
 * Отдельным файлом и без единого импорта из приложения: проверка положения
 * файла не должна зависеть от того, удалось ли этот файл загрузить. Когда он
 * лежал в корне проекта — а Next ищет его рядом с `app/` — набор падал на
 * сборке модуля, и по такому падению нельзя было понять, что именно не так.
 *
 * Тогда защита не работала вовсе: `/marketing`, `/sales`, `/insights` и
 * `/settings` отдавали 200 с полным содержимым вообще без печенья, а все
 * тесты оставались зелёными. Код, который не исполняется, не падает.
 */

import { existsSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = path.resolve(__dirname, "../..");

describe("proxy.ts лежит там, где Next его ищет", () => {
  it("стоит рядом с app/, то есть под src/", () => {
    expect(
      existsSync(path.join(FRONTEND_ROOT, "src/proxy.ts")),
      "src/proxy.ts отсутствует — Next не загрузит защиту, и весь кабинет " +
        "откроется без печенья, не уронив при этом ни одного теста",
    ).toBe(true);
  });

  it.each(["proxy.ts", "middleware.ts", "src/middleware.ts"])(
    "%s не оставлен там, откуда он не загрузится",
    (stray) => {
      expect(
        existsSync(path.join(FRONTEND_ROOT, stray)),
        `${stray} не должен существовать: Next читает только src/proxy.ts, ` +
          "а лишний файл рядом создаёт видимость защиты",
      ).toBe(false);
    },
  );
});
