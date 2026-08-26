import { notFound } from "next/navigation";
import { AnalyticsScreen } from "@/components/portal/screens/analytics";
import { AppearanceScreen } from "@/components/portal/screens/appearance";
import { ConversationsScreen } from "@/components/portal/screens/conversations";
import { InstallScreen } from "@/components/portal/screens/install";
import { KnowledgeScreen } from "@/components/portal/screens/knowledge";
import { screensOf } from "@/lib/agent-screens";
import { isLocked } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";

/**
 * Экран агента.
 *
 * Права проверяются здесь, а не только вкладками. Вкладку запертому агенту
 * не рисуют, но адрес набирается и без вкладки — ровно так уже находили
 * скрытые экраны в панели движка.
 */
const SCREENS: Record<string, () => React.ReactElement> = {
  conversations: ConversationsScreen,
  analytics: AnalyticsScreen,
  knowledge: KnowledgeScreen,
  appearance: AppearanceScreen,
  install: InstallScreen,
};

export default async function AgentScreenPage({
  params,
}: {
  params: Promise<{ id: string; screen: string }>;
}) {
  const { id, screen } = await params;
  const nav = await loadPortalNav();

  const agent = nav.agents.find((a) => a.id === id);
  if (!agent || isLocked(agent.access)) notFound();
  if (!screensOf(id).some((s) => s.id === screen)) notFound();

  const Screen = SCREENS[screen];
  if (!Screen) notFound();

  return <Screen />;
}
