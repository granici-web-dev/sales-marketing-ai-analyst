"use client";

/**
 * Переключатель темы.
 *
 * Три состояния, а не два. «Как в системе» — тоже выбор, и он же по умолчанию:
 * бинарной паре пришлось бы врать о том, что происходит, пока человек ничего
 * не выбрал.
 *
 * Выбор запоминается в браузере, а не в базе: это свойство рабочего места,
 * а не учётной записи. У одного директора рабочий стол стоит у окна, а ноутбук
 * он открывает дома вечером.
 *
 * Переехало из панели движка вместе с экранами: снести панель, не перенеся
 * переключатель, значило бы отнять у клиента работающую возможность.
 */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

export type ThemeChoice = "system" | "light" | "dark";

/** Ключ в localStorage. Тот же, что был в панели, — выбор клиента переживает переезд. */
export const THEME_KEY = "aw-theme";

/**
 * Применение выбора: разметка портала уже понимает `data-theme`.
 *
 * «Как в системе» — это ОТСУТСТВИЕ атрибута, а не его третье значение:
 * `prefers-color-scheme` работает только тогда, когда его никто не перебивает.
 */
export function applyTheme(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
}

/**
 * Тот же выбор, применённый ДО первой отрисовки.
 *
 * Строкой для инлайн-скрипта, потому что React выполнится уже после того, как
 * браузер покажет страницу: без этого выбравший тёмную тему видел бы вспышку
 * светлой на каждом переходе. `try` — на случай браузера, где хранилище
 * запрещено: тема не повод не открыть кабинет.
 */
export const THEME_BOOTSTRAP = `try{var c=localStorage.getItem(${JSON.stringify(
  THEME_KEY,
)});if(c==="light"||c==="dark")document.documentElement.setAttribute("data-theme",c)}catch(e){}`;

const OPTIONS: ThemeChoice[] = ["system", "light", "dark"];

export function ThemeSwitch() {
  const t = useTranslations("theme");

  /* Читается в эффекте, а не в инициализаторе: на сервере `localStorage` не
     существует, а прочитанное в инициализаторе значение разошлось бы с тем,
     что сервер уже отрисовал. Вспышку предотвращает не это состояние,
     а THEME_BOOTSTRAP выше. */
  const [choice, setChoice] = useState<ThemeChoice>("system");

  useEffect(() => {
    try {
      const stored = localStorage.getItem(THEME_KEY);
      if (stored === "light" || stored === "dark") setChoice(stored);
    } catch {
      /* хранилище запрещено — остаётся «как в системе» */
    }
  }, []);

  const pick = (next: ThemeChoice) => {
    setChoice(next);
    applyTheme(next);
    try {
      if (next === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, next);
    } catch {
      /* выбор не переживёт перезагрузку, но эту страницу перекрасит */
    }
  };

  return (
    <div
      role="group"
      aria-label={t("label")}
      className="flex gap-0.5 rounded-control border p-0.5"
    >
      {OPTIONS.map((id) => (
        <button
          key={id}
          type="button"
          aria-pressed={choice === id}
          onClick={() => pick(id)}
          className={
            choice === id
              ? "flex-1 rounded-[inherit] bg-muted px-2 py-1 text-xs"
              : "flex-1 rounded-[inherit] px-2 py-1 text-xs text-muted-foreground hover:bg-muted/50"
          }
        >
          {t(id)}
        </button>
      ))}
    </div>
  );
}
