"use client";

/**
 * Вкладки агента.
 *
 * Подчёркивание, а не заливка: вкладка — это край страницы, а не кнопка.
 * Заливка спорила бы с активным агентом в меню слева, и на экране оказалось
 * бы два «выбранного».
 *
 * Полоса прокручивается по горизонтали на узком экране, а не переносится и
 * не прячется в «ещё»: шесть вкладок — это шесть, и порядок у них осмысленный.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

export interface AgentTab {
  href: string;
  labelKey: string;
}

export function AgentTabs({
  tabs,
  namespace,
  label,
}: {
  tabs: AgentTab[];
  /** Пространство переводов, откуда берутся подписи вкладок. */
  namespace: string;
  /** Чем полоса представляется вспомогательным технологиям. */
  label: string;
}) {
  const pathname = usePathname();
  const t = useTranslations(namespace);

  return (
    <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
      <nav className="flex w-max gap-1 border-b" aria-label={label}>
        {tabs.map((tab) => {
          const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={[
                "-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
                active
                  ? "border-primary font-medium text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              {t(tab.labelKey)}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
