/**
 * Каждая строка словаря обязана разбираться как ICU-сообщение.
 *
 * next-intl читает фигурные скобки как подстановку. Строка, где скобка стоит
 * просто так — например, в примере вида `{{secret}}`, — валит отрисовку целой
 * страницы, и валит её только на том языке, где эту строку написали. Типы
 * такого не ловят, сборка тоже: словарь для них обычный JSON.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { createTranslator } from "next-intl";
import { describe, expect, it } from "vitest";

const MESSAGES = path.resolve(__dirname, "../../messages");

/** Все листья словаря как пары «путь → строка». */
function leaves(node: unknown, at: string[] = []): Array<[string, string]> {
  if (typeof node === "string") return [[at.join("."), node]];
  if (node === null || typeof node !== "object") return [];
  return Object.entries(node as Record<string, unknown>).flatMap(([k, v]) =>
    leaves(v, [...at, k]),
  );
}

/** Имена подстановок в сообщении: `{when}` → `when`. */
const placeholders = (message: string): string[] =>
  [...message.matchAll(/\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,}]/g)].map(
    (m) => m[1]!,
  );

describe.each(["ro", "en"])("словарь %s", (locale) => {
  const dict = JSON.parse(
    readFileSync(path.join(MESSAGES, `${locale}.json`), "utf8"),
  );
  const all = leaves(dict);

  it("строки вообще нашлись — иначе перебор ниже проверяет воздух", () => {
    expect(all.length).toBeGreaterThan(100);
  });

  it.each(all)("%s разбирается", (key, message) => {
    // Ошибку надо перехватывать, а не ждать исключения: next-intl её не бросает,
    // а сообщает в `onError` и возвращает вместо текста сам ключ. Проверка вида
    // `not.toThrow()` здесь проходит на любом сломанном сообщении — проверено.
    const failures: string[] = [];
    const t = createTranslator({
      locale,
      messages: dict,
      onError: (err) => failures.push(err.message),
    });

    // Подстановки заполняются заглушками: без них разборщик пожалуется на
    // отсутствующее значение, а проверяем мы разбор самой строки.
    const values = Object.fromEntries(
      placeholders(message).map((name) => [name, "1"]),
    );
    const rendered = t(key, values);

    expect(failures, `${key}: ${message}`).toEqual([]);
    expect(
      rendered,
      "сломанное сообщение отрисовывается как собственный ключ",
    ).not.toBe(key);
  });
});
