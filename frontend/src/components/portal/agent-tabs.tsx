"use client";

/**
 * Вкладки агента.
 *
 * Заголовок агента стоит над вкладками, а не в топбаре: человек должен
 * видеть, у кого он, и где именно, одним взглядом и в одном месте.
 *
 * Полоса прокручивается по горизонтали на узком экране, а не переносится
 * и не прячется в «ещё»: шесть вкладок — это шесть, и порядок у них
 * осмысленный, от воронки к настройкам.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTranslations } from "next-intl";

export interface AgentTab {
  href: string;
  labelKey: string;
}

export function AgentTabs({ agentId, tabs }: { agentId: string; tabs: AgentTab[] }) {
  const pathname = usePathname();
  const t = useTranslations("nav");
  const tAgents = useTranslations("agents");

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold tracking-tight">{tAgents(`names.${agentId}`)}</h1>

      <div className="-mx-4 overflow-x-auto px-4 md:mx-0 md:px-0">
        <nav className="flex w-max gap-1 border-b" aria-label={tAgents(`names.${agentId}`)}>
          {tabs.map((tab) => {
            const active = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={[
                  // Подчёркивание вместо заливки: вкладка — это край страницы,
                  // а не кнопка. Заливка спорила бы с активным агентом слева.
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
    </div>
  );
}
