import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowRight, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  fetchPortalAgents,
  PORTAL_AGENTS_ARE_STUBBED,
  type AgentAccess,
  type PortalAgent,
} from "@/lib/portal-agents";

/* Ведомость, а не сетка карточек. Человек пришёл посмотреть, что у него
   есть и чего нет, — это список владений, и читается он строками: имя
   слева, состояние и действие справа, одинаково на каждой строке. Семь
   одинаковых карточек с иконкой и заголовком заставляли бы сравнивать
   взглядом по диагонали. */

const TONE: Record<AgentAccess, "ok" | "warn" | "neutral"> = {
  unlocked: "ok",
  expiring: "warn",
  locked: "neutral",
  unavailable: "neutral",
};

export default async function AgentsPage() {
  const t = await getTranslations("agents");
  const agents = await fetchPortalAgents();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{t("heading")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("lead")}</p>
      </div>

      {PORTAL_AGENTS_ARE_STUBBED && (
        <p className="rounded-control border border-warn/30 bg-warn/10 px-4 py-3 text-sm text-warn">
          {t("stubNotice")}
        </p>
      )}

      <ul className="divide-y divide-border overflow-hidden rounded-card border bg-card">
        {agents.map((agent) => (
          <AgentRow key={agent.id} agent={agent} />
        ))}
      </ul>
    </div>
  );
}

async function AgentRow({ agent }: { agent: PortalAgent }) {
  const t = await getTranslations("agents");
  const open = agent.access === "unlocked" || agent.access === "expiring";

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:px-5">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {!open && (
            <Lock size={13} className="shrink-0 text-muted-foreground" aria-hidden="true" />
          )}
          <span className="font-medium">{t(`names.${agent.id}`)}</span>
          <Badge variant={TONE[agent.access]}>{t(`access.${agent.access}`)}</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{t(`short.${agent.id}`)}</p>
        {agent.access === "expiring" && agent.daysLeft !== null && (
          /* Срок называется заранее, а не в день отключения: человек должен
             успеть продлить, а не обнаружить закрытый раздел. */
          <p className="mt-1 text-sm text-warn">{t("daysLeft", { days: agent.daysLeft })}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {agent.access === "locked" && agent.priceFrom !== null && (
          <>
            <span className="text-sm text-muted-foreground tabular-nums">
              {t("priceFrom", { price: agent.priceFrom })}
            </span>
            <button
              type="button"
              className="rounded-control bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
            >
              {t("unlock")}
            </button>
          </>
        )}

        {agent.access === "unavailable" && (
          /* Ни цены, ни кнопки. Оплата за непостроенного агента — это деньги
             за обещание, и никакая формулировка этого не исправляет. */
          <span className="text-sm text-muted-foreground">{t("comingSoon")}</span>
        )}

        {open &&
          (agent.href ? (
            <Link
              href={agent.href}
              className="inline-flex items-center gap-1.5 rounded-control border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              {t("open")}
              <ArrowRight size={14} aria-hidden="true" />
            </Link>
          ) : (
            /* Открыт, но экранов здесь ещё нет: они живут в кабинете движка,
               пока не перенесены. Врать кнопкой, которая никуда не ведёт,
               хуже, чем сказать это. */
            <span className="text-sm text-muted-foreground">{t("elsewhere")}</span>
          ))}
      </div>
    </li>
  );
}
