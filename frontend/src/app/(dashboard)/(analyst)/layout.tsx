import { getTranslations } from "next-intl/server";
import DataFreshnessBanner from "@/components/data-freshness-banner";
import { AgentTabs, type AgentTab } from "@/components/portal/agent-tabs";

/**
 * Второй уровень — вкладки внутри агента.
 *
 * У аналитика шесть экранов, и они одного агента, а не шесть пунктов меню
 * наравне с чат-ботом. Вкладки говорят это самой формой: пока ты внутри
 * аналитика, слева подсвечен он, а сверху видно, где именно ты у него.
 *
 * Группа маршрутов, а не сегмент: адреса /marketing, /sales и прочие
 * существовали раньше портала. Скобки в имени папки в адрес не попадают,
 * поэтому вкладка появилась, а ссылки остались прежними.
 */
const TABS: AgentTab[] = [
  { href: "/marketing", labelKey: "marketing" },
  { href: "/sales", labelKey: "sales" },
  { href: "/salespeople", labelKey: "salespeople" },
  { href: "/insights", labelKey: "insights" },
  { href: "/chat", labelKey: "chat" },
  { href: "/integrations", labelKey: "integrations" },
];

export default async function AnalystLayout({ children }: { children: React.ReactNode }) {
  const t = await getTranslations("agents");
  const name = t("names.data-analyst");

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <h1 className="text-xl font-semibold tracking-tight">{name}</h1>
        <AgentTabs tabs={TABS} namespace="nav" label={name} />
      </div>
      {/* Свежесть данных — свойство аналитика: он один тянет их из CRM. */}
      <DataFreshnessBanner />
      {children}
    </div>
  );
}
