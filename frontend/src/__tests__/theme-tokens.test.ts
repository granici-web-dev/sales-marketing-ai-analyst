/**
 * Подметание исходников: цвет, не зависящий от темы, не должен вернуться.
 *
 * Кабинет умеет светлую и тёмную тему, и переключатель у клиента на виду.
 * Но тему знают только токены: `bg-yellow-100`, `#71717A` и `hsl(221 83% 53%)`
 * имеют одно значение на обе, и написанные в разметке они оставляют светлые
 * пятна на тёмной странице и серые оси на графиках. Так и было — 159 таких
 * значений в 35 файлах, — и заметить это глазами можно только открыв каждый
 * экран в обеих темах.
 *
 * Проверка смотрит в исходники, а не в отрисованное: отрисованное покрыть
 * целиком невозможно, а строка в файле либо есть, либо нет.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(process.cwd(), "src");

const PATTERNS: { name: string; re: RegExp }[] = [
  {
    name: "палитра Tailwind",
    re: /\b(?:bg|text|border|stroke|fill|ring|divide)-(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|slate|gray|zinc|neutral|stone)-\d{2,3}\b/,
  },
  { name: "белое или чёрное словом", re: /\b(?:bg|text|border|divide|fill|stroke)-(?:white|black)\b/ },
  { name: "шестнадцатеричный цвет", re: /#[0-9A-Fa-f]{6}\b/ },
  {
    name: "литеральный hsl()",
    // Не только в скобках Tailwind: `stroke="hsl(240 6% 90%)"` в свойстве
    // JSX — то же самое, и на нём эта проверка один раз уже промахнулась.
    // `var(--…)` не ловится: цветовые функции поверх токена законны.
    re: /(?<!var\(--[\w-]{0,40}\)[^)]{0,40})\b(?:hsla?|rgba?)\(\s*[\d.]/,
  },
];

/**
 * Затемнение под модальным окном. Это не цвет темы, а вуаль: она обязана
 * быть тёмной и в светлой теме тоже, иначе не отделяет окно от страницы.
 */
const ALLOWED = [/bg-black\/\d+/];

/**
 * Комментарий — это объяснение, а не разметка, и в нём цвет назвать можно:
 * badge.tsx именно так и объясняет, почему `bg-yellow-100` не взяли.
 *
 * Вырезаются оба вида, блочный и строчный, с сохранением переводов строк —
 * иначе номера строк в отчёте разъедутся с файлом. Проверка по началу строки
 * не годилась: продолжение блочного комментария звёздочки не имеет.
 */
function stripComments(source: string): string {
  const keepNewlines = (s: string): string => s.replace(/[^\n]/g, " ");
  return source
    .replace(/\/\*[\s\S]*?\*\//g, keepNewlines)
    .replace(/\/\/[^\n]*/g, keepNewlines);
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return /\.tsx?$/.test(entry) ? [full] : [];
  });
}

describe("цвета берутся из токенов темы", () => {
  const files = walk(ROOT);

  it("исходники найдены", () => {
    expect(files.length).toBeGreaterThan(50);
  });

  it("ни одного цвета мимо токенов", () => {
    const offences: string[] = [];

    for (const file of files) {
      // Сам себя эта проверка содержит в виде регулярных выражений.
      if (file.endsWith("theme-tokens.test.ts")) continue;

      const lines = stripComments(readFileSync(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        let rest = line;
        for (const allow of ALLOWED) rest = rest.replace(allow, "");
        for (const { name, re } of PATTERNS) {
          const hit = re.exec(rest);
          if (hit) {
            offences.push(
              `${file.slice(ROOT.length + 1)}:${i + 1} — ${name}: ${hit[0]}`,
            );
          }
        }
      });
    }

    expect(offences).toEqual([]);
  });
});
