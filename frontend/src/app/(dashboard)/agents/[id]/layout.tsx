import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { AgentTabs } from "@/components/portal/agent-tabs";
import { screensOf } from "@/lib/agent-screens";
import { isLocked, isScreenVisible } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";
import type { AgentAccess } from "@/lib/portal-agents";

const TONE: Record<AgentAccess, "ok" | "warn" | "neutral"> = {
  unlocked: "ok",
  expiring: "warn",
  locked: "neutral",
  unavailable: "neutral",
};

/**
 * Шапка агента и его вкладки.
 *
 * В раскладке, а не на каждой странице: имя агента и состояние не должны
 * мигать при переходе между его вкладками — это один и тот же агент.
 *
 * Запертому вкладок не показываем. Вкладка, ведущая к настройкам того, чего
 * у человека нет, — это приглашение потрогать чужое.
 *
 * Скрытые экраны тоже не рисуем: движок отвечает на них отказом, и вкладка,
 * ведущая к сообщению «раздел недоступен», хуже отсутствующей вкладки.
 */
export default async function AgentLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const t = await getTranslations("agents");
  const nav = await loadPortalNav();

  const agent = nav.agents.find((a) => a.id === id);
  if (!agent) notFound();

  const locked = isLocked(agent.access);
  const screens = locked
    ? []
    : screensOf(agent.id).filter((s) =>
        isScreenVisible(nav.hiddenScreens, s.id),
      );

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          {locked && (
            <Lock
              size={15}
              className="text-muted-foreground"
              aria-hidden="true"
            />
          )}
          <h1 className="text-xl font-semibold tracking-tight">
            {t(`names.${agent.id}`)}
          </h1>
          <Badge variant={TONE[agent.access]}>
            {t(`access.${agent.access}`)}
          </Badge>
        </div>

        {screens.length > 0 && (
          <AgentTabs
            tabs={screens.map((s) => ({
              href: `/agents/${agent.id}/${s.id}`,
              labelKey: s.id,
            }))}
            namespace="agentScreens"
            label={t(`names.${agent.id}`)}
          />
        )}
      </div>

      {children}
    </div>
  );
}
