import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { UnlockPanel } from "@/components/portal/unlock-panel";
import { loadPortalNav } from "@/lib/portal-nav.server";
import type { AgentAccess } from "@/lib/portal-agents";

/**
 * Страница агента, у которого нет экранов в этом кабинете.
 *
 * Шесть агентов из семи работают в движке, и вести туда кнопкой — честнее,
 * чем рисовать здесь их подобие. Страница отвечает на один вопрос: что это
 * за агент и что с ним сейчас можно сделать.
 *
 * Кнопка «включить» ведёт в раздел абонемента движка, где оплата
 * действительно есть. Поагентной покупки пока нет нигде, и кнопка, которая
 * ничего не делает, была бы хуже её отсутствия.
 */
const TONE: Record<AgentAccess, "ok" | "warn" | "neutral"> = {
  unlocked: "ok",
  expiring: "warn",
  locked: "neutral",
  unavailable: "neutral",
};

export default async function AgentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("agents");
  const nav = await loadPortalNav();

  const agent = nav.agents.find((a) => a.id === id);
  if (!agent) notFound();

  const locked = agent.access === "locked";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <div className="flex items-center gap-2">
          {locked && <Lock size={15} className="text-muted-foreground" aria-hidden="true" />}
          <h1 className="text-xl font-semibold tracking-tight">{t(`names.${agent.id}`)}</h1>
          <Badge variant={TONE[agent.access]}>{t(`access.${agent.access}`)}</Badge>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {t(`short.${agent.id}`)}
        </p>
      </div>

      <div className="rounded-card border bg-card p-5">
        {agent.access === "unavailable" && (
          <p className="text-sm text-muted-foreground">{t("page.unavailable")}</p>
        )}

        {locked &&
          (agent.plan ? (
            <UnlockPanel plan={agent.plan} />
          ) : (
            /* Ни один покупаемый тариф его не даёт. Кнопка, ведущая к отказу
               «этот пакет ещё не продаётся», хуже отсутствия кнопки. */
            <p className="text-sm text-muted-foreground">{t("page.notPurchasable")}</p>
          ))}

        {(agent.access === "unlocked" || agent.access === "expiring") && (
          <>
            <p className="text-sm">{t("page.running")}</p>
            {agent.access === "expiring" && agent.daysLeft !== null && (
              <p className="mt-2 text-sm text-warn">
                {t("daysLeft", { days: agent.daysLeft })}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
