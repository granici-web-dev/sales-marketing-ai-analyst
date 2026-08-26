import { redirect } from "next/navigation";
import { isLocked } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";

/**
 * У портала нет своей главной.
 *
 * Обзор поверх списка агентов был бы страницей о странице: слева уже видно
 * всё, что у клиента есть. Поэтому корень ведёт к первому работающему
 * агенту, а если не работает ни один — в абонемент, то есть туда, где это
 * можно исправить.
 */
export default async function PortalRoot() {
  const nav = await loadPortalNav();
  const first = nav.agents.find((agent) => !isLocked(agent.access));
  redirect(first ? first.href : "/subscription");
}
