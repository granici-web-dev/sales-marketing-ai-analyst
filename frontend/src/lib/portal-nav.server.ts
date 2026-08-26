/**
 * Серверная половина навигации: спросить движок, что у клиента есть.
 *
 * Отдельным файлом, потому что `next/headers` в браузере не существует, а
 * типы и правила из `portal-nav.ts` нужны клиентскому меню. Граница проходит
 * здесь и видна по имени файла.
 */
import { cache } from "react";
import { engineGet } from "@/lib/engine";
import { fetchPortalAgents } from "@/lib/portal-agents";
import { HOST_AGENT, HOST_AGENT_NAV, type PortalNav } from "@/lib/portal-nav";

/**
 * `cache` — на один проход отрисовки.
 *
 * Оболочку рисует раскладка, содержимое — страница, и обе спрашивают одно и
 * то же. Без этого каждый переход стоил бы движку двух запросов вместо одного.
 */
export const loadPortalNav = cache(async (): Promise<PortalNav> => {
  // Оба запроса разом: они не зависят друг от друга, а последовательно
  // сложились бы в задержку на каждой странице кабинета.
  const [result, me] = await Promise.all([
    fetchPortalAgents(),
    engineGet<{
      email: string;
      tenant: { name: string; hiddenScreens?: string[] } | null;
    }>("/admin/api/me"),
  ]);

  if (!result.ok) {
    return {
      agents: [HOST_AGENT_NAV],
      account: null,
      linked: false,
      hiddenScreens: [],
    };
  }

  return {
    linked: true,
    // Пустой список, если движок не ответил: у аналитика своих скрытых экранов
    // нет, а рисовать чужие вкладки всё равно нечем — агентов движка в этом
    // случае в списке не будет.
    hiddenScreens: me.ok ? (me.data.tenant?.hiddenScreens ?? []) : [],
    account: me.ok
      ? { email: me.data.email, tenantName: me.data.tenant?.name ?? null }
      : null,
    agents: result.data.map((agent) =>
      agent.id === HOST_AGENT
        ? HOST_AGENT_NAV
        : {
            id: agent.id,
            access: agent.access,
            href: `/agents/${agent.id}`,
            daysLeft: agent.daysLeft,
            priceFrom: agent.priceFrom,
            plan: agent.plan,
            tiers: agent.tiers,
          },
    ),
  };
});
