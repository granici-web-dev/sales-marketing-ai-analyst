import { getTranslations } from "next-intl/server";
import { notFound } from "next/navigation";
import { ArrowUpRight, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { engineBaseUrl } from "@/lib/engine";
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

  const enginePanel = `${engineBaseUrl()}/admin`;
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

        {locked && (
          <>
            <p className="text-sm">{t("page.locked")}</p>
            {agent.priceFrom !== null && (
              <p className="mt-2 text-sm tabular-nums text-muted-foreground">
                {t("priceFrom", { price: agent.priceFrom })}
              </p>
            )}
            <a
              href={enginePanel}
              className="mt-4 inline-flex items-center gap-1.5 rounded-control bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              {t("unlock")}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </>
        )}

        {(agent.access === "unlocked" || agent.access === "expiring") && (
          <>
            <p className="text-sm">{t("page.elsewhere")}</p>
            {agent.access === "expiring" && agent.daysLeft !== null && (
              <p className="mt-2 text-sm text-warn">
                {t("daysLeft", { days: agent.daysLeft })}
              </p>
            )}
            <a
              href={enginePanel}
              className="mt-4 inline-flex items-center gap-1.5 rounded-control border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              {t("open")}
              <ArrowUpRight size={14} aria-hidden="true" />
            </a>
          </>
        )}
      </div>
    </div>
  );
}
