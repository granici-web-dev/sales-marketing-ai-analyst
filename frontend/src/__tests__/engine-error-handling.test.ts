/**
 * Подметание: экран, который ходит в движок, обязан уметь ответить
 * на протухшую сессию.
 *
 * Три экрана — «Аналитика», «Внешний вид», «Установка» — этого не умели.
 * Их `catch` показывал `err.message`, а у EngineUnauthorized это наша
 * служебная строка «engine session expired»: румынскому директору
 * показывали английскую фразу из нашего кода и оставляли на экране,
 * который больше ничего не покажет.
 *
 * Проверка смотрит в исходники, а не в отрисованное, и это осознанный
 * размен. Отрисовать девять экранов с подменённым движком дороже, а поймать
 * этим можно ровно то же: разница между рабочим и сломанным экраном здесь —
 * одна строка импорта. Само поведение проверено отдельно и по-настоящему,
 * в lib/__tests__/engine-client.test.ts.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const PORTAL = join(process.cwd(), "src", "components", "portal");

/**
 * Экран, отвечающий на 401 переводом, а не перезагрузкой.
 *
 * Панель ввода кода — единственное место, где перезагрузка была бы враждебной:
 * человек в середине ввода, и страница увезла бы его вместе с набранным.
 */
const ANSWERS_IN_WORDS = ["unlock-panel.tsx"];

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return entry.endsWith(".tsx") ? [full] : [];
  });
}

describe("отказ движка на экранах кабинета", () => {
  const files = walk(PORTAL)
    .map((f) => ({ path: f, source: readFileSync(f, "utf8") }))
    .filter((f) => /\bengineApi\b/.test(f.source));

  it("экраны, ходящие в движок, вообще найдены", () => {
    expect(files.length).toBeGreaterThanOrEqual(8);
  });

  it("каждый умеет ответить на протухшую сессию", () => {
    const deaf = files
      .filter(({ path, source }) => {
        const name = path.split("/").pop()!;
        if (ANSWERS_IN_WORDS.includes(name)) return !/EngineUnauthorized/.test(source);
        return !/reportEngineError|EngineUnauthorized/.test(source);
      })
      .map(({ path }) => path.slice(PORTAL.length + 1));

    expect(deaf).toEqual([]);
  });

  it("никто не читает err.message сам", () => {
    // Именно так на экран и попадало «engine session expired»: обработчик
    // брал текст у ошибки, не спросив, что это за ошибка. Текст берётся
    // у reportEngineError — он про сессию знает.
    //
    // Разбор JSON из поля ввода отказом движка не является, и там читать
    // сообщение правильно; такая строка помечается на месте.
    const MARK = "не отказ движка";

    const raw: string[] = [];
    for (const { path, source } of files) {
      const lines = source.split("\n");
      lines.forEach((line, i) => {
        if (!/\(err(?:or)? as Error\)\.message|\berr\.message\b/.test(line)) return;
        const nearby = lines.slice(Math.max(0, i - 4), i).join("\n");
        if (nearby.includes(MARK)) return;
        raw.push(`${path.slice(PORTAL.length + 1)}:${i + 1}`);
      });
    }

    expect(raw).toEqual([]);
  });
});
