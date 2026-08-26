import { getTranslations } from "next-intl/server";
import { notFound, redirect } from "next/navigation";
import { UnlockPanel } from "@/components/portal/unlock-panel";
import { screensOf } from "@/lib/agent-screens";
import { isLocked } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";

/**
 * Корень агента.
 *
 * Есть экраны — ведём на первый: пустая страница под вкладками была бы
 * страницей ни о чём. Заперт — здесь и стоит предложение включить.
 */
export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("agents");
  const nav = await loadPortalNav();

  const agent = nav.agents.find((a) => a.id === id);
  if (!agent) notFound();

  const locked = isLocked(agent.access);
  const screens = screensOf(agent.id);
  if (!locked && screens.length > 0) redirect(`/agents/${agent.id}/${screens[0]!.id}`);

  return (
    <div className="max-w-2xl">
      <p className="mb-4 text-sm leading-relaxed text-muted-foreground">
        {t(`short.${agent.id}`)}
      </p>

      <div className="rounded-card border bg-card p-5">
        {agent.access === "unavailable" && (
          <p className="text-sm text-muted-foreground">{t("page.unavailable")}</p>
        )}

        {agent.access === "locked" &&
          (agent.tiers ? (
            <UnlockPanel agentId={agent.id} tiers={agent.tiers} />
          ) : (
            /* Цены нет — продавать нечего. Кнопка, ведущая к отказу «у этого
               агента нет цены», хуже отсутствия кнопки. */
            <p className="text-sm text-muted-foreground">{t("page.notPurchasable")}</p>
          ))}

        {(agent.access === "unlocked" || agent.access === "expiring") && (
          <>
            <p className="text-sm">{t("page.running")}</p>
            {agent.access === "expiring" && agent.daysLeft !== null && (
              <p className="mt-2 text-sm text-warn">{t("daysLeft", { days: agent.daysLeft })}</p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
