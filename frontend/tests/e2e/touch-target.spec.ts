/**
 * Дорогая половина проверки цели нажатия: настоящие пиксели.
 *
 * `touch-target.test.tsx` читает классы — jsdom не считает Tailwind, и высоту
 * там взять неоткуда. Это оставляет незакрытым ровно одно: класс написан, а на
 * экране его нет. Так уже было в этом репозитории с `proxy.ts` — совершенно
 * правильная функция в файле, который никто не загружал.
 *
 * Поэтому здесь берётся `boundingBox()` у собранного приложения. Страница
 * входа выбрана потому, что она открыта без сессии и держит оба примитива
 * рядом: два поля и кнопку. Ничего подменять не нужно.
 */
import { expect, test } from "@playwright/test";

/** D-24 (07-UI-SPEC §280): 44 px по высоте и ширине, на всех ширинах экрана. */
const FLOOR_PX = 44;

test("на странице входа все контролы не ниже 44 px", async ({ page }) => {
  await page.goto("/login");

  const controls = page.locator("button, input:not([type=hidden])");
  const count = await controls.count();
  // Если разметка изменится и контролов не станет, проверка обязана упасть,
  // а не пройти по пустому списку.
  expect(count).toBeGreaterThan(0);

  for (let i = 0; i < count; i += 1) {
    const control = controls.nth(i);
    const box = await control.boundingBox();
    expect(box, `контрол ${i} не отрисован`).not.toBeNull();
    expect(
      Math.round(box!.height),
      `${await control.evaluate((el) => el.outerHTML.slice(0, 80))}`,
    ).toBeGreaterThanOrEqual(FLOOR_PX);
  }
});
