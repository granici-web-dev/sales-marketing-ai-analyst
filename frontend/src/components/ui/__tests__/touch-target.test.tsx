/**
 * Цель нажатия у примитивов — не меньше 44 px.
 *
 * D-24 требует этого от всех контролов и на всех ширинах (07-UI-SPEC §280),
 * но требование выполнялось руками: кнопка приходила из shadcn на 36 px,
 * «маленькая» — на 32, и семь мест дописывали `min-h-11` поверх примитива.
 * Тридцать семь кнопок из сорока четырёх промахивались мимо пальца, и
 * увидеть это можно было только открыв каждый экран с телефона.
 *
 * Половины две, как у защиты маршрутов. Первая читает классы отрисованного
 * примитива: jsdom не считает Tailwind и вернул бы ноль для любой высоты,
 * поэтому классы переводятся в пиксели по шкале — `h-11` это 11 × 4 px.
 * Вторая смотрит в исходники и следит, чтобы разметка не начала дописывать
 * пол обратно: накладка в разметке означает, что примитив его не даёт, и
 * следующая кнопка снова промахнётся.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, type ButtonProps } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

/** Шаг шкалы Tailwind: `h-11` → 11 × 4 px = 44 px. */
const STEP_PX = 4;
const FLOOR_PX = 44;

/**
 * Пол по классам: `h-9 min-h-11` даёт 44 — `min-height` перебивает `height`,
 * и именно так работали ручные накладки. Поэтому берётся максимум, а не
 * последнее объявление.
 */
function floorPx(classes: string, axis: "h" | "w"): number {
  const found: number[] = [];
  const scale = new RegExp(
    `(?:^|\\s)(?:min-)?(?:${axis}|size)-(\\d+(?:\\.\\d+)?)(?=\\s|$)`,
    "g",
  );
  const arbitrary = new RegExp(
    `(?:^|\\s)(?:min-)?(?:${axis}|size)-\\[(\\d+)px\\](?=\\s|$)`,
    "g",
  );
  for (const m of classes.matchAll(scale)) found.push(Number(m[1]) * STEP_PX);
  for (const m of classes.matchAll(arbitrary)) found.push(Number(m[1]));
  return found.length > 0 ? Math.max(...found) : 0;
}

const SIZES: NonNullable<ButtonProps["size"]>[] = ["default", "sm", "lg", "icon"];

describe("цель нажатия в примитиве", () => {
  it.each(SIZES)("кнопка размера %s не ниже 44 px", (size) => {
    render(<Button size={size}>да</Button>);
    expect(floorPx(screen.getByRole("button").className, "h")).toBeGreaterThanOrEqual(
      FLOOR_PX,
    );
  });

  /* Ширина названа в спецификации отдельно и важна там, где её задаёт не
     текст: у кнопки-значка внутри одна иконка на 16 px. */
  it("кнопка-значок не уже 44 px", () => {
    render(
      <Button size="icon" aria-label="закрыть">
        ×
      </Button>,
    );
    expect(floorPx(screen.getByRole("button").className, "w")).toBeGreaterThanOrEqual(
      FLOOR_PX,
    );
  });

  /* Поле — такая же цель нажатия, и стоит с кнопкой в одном ряду. */
  it("поле ввода не ниже 44 px", () => {
    render(<Input aria-label="адрес" />);
    expect(floorPx(screen.getByRole("textbox").className, "h")).toBeGreaterThanOrEqual(
      FLOOR_PX,
    );
  });
});

/* ── Вторая половина: пол принадлежит примитиву, а не разметке ─────────── */

const ROOT = join(process.cwd(), "src");
const OWNED_BY_PRIMITIVE = ["Button", "Input"];
const FLOOR_IN_MARKUP = /min-h-(?:11\b|\[44px\])/g;

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) return walk(full);
    return full.endsWith(".tsx") ? [full] : [];
  });
}

/**
 * Чей это класс — определяется ближайшим `<` слева: className стоит в самом
 * открывающем теге, даже когда завёрнут в `cn(...)`. Внутри тега других `<`
 * нет, поэтому поиск назад попадает именно в имя элемента.
 */
function tagBefore(source: string, index: number): string {
  const open = source.lastIndexOf("<", index);
  return open === -1 ? "" : (/^<\/?([A-Za-z][\w.]*)/.exec(source.slice(open))?.[1] ?? "");
}

describe("пол принадлежит примитиву", () => {
  it("разметка не дописывает 44 px поверх Button и Input", () => {
    const offenders: string[] = [];
    for (const file of walk(ROOT)) {
      const source = readFileSync(file, "utf8");
      for (const m of source.matchAll(FLOOR_IN_MARKUP)) {
        const tag = tagBefore(source, m.index);
        if (!OWNED_BY_PRIMITIVE.includes(tag)) continue;
        const line = source.slice(0, m.index).split("\n").length;
        offenders.push(`${file.slice(ROOT.length + 1)}:${line} — <${tag}>`);
      }
    }
    expect(offenders).toEqual([]);
  });
});
