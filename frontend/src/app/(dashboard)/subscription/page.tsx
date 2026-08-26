import { getTranslations } from "next-intl/server";
import Link from "next/link";
import { ArrowRight, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PlanPanel } from "@/components/portal/plan";
import { PortalSignIn } from "@/components/portal/portal-sign-in";
import { isLocked, type NavAgent } from "@/lib/portal-nav";
import { loadPortalNav } from "@/lib/portal-nav.server";
import type { AgentAccess } from "@/lib/portal-agents";

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

export default async function SubscriptionPage() {
  const t = await getTranslations("agents");
  const nav = await loadPortalNav();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          {t("subscriptionHeading")}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("subscriptionLead")}
        </p>
      </div>

      {/* Не вошёл — на месте ведомости вход, а не семь замков. Семь замков
          были бы враньём: мы не знаем, что куплено, пока не знаем, кто он. */}
      {nav.linked ? (
        <ul className="divide-y divide-border overflow-hidden rounded-card border bg-card">
          {nav.agents.map((agent) => (
            <AgentRow key={agent.id} agent={agent} />
          ))}
        </ul>
      ) : (
        <PortalSignIn />
      )}

      {/* Тариф ниже ведомости, а не вместо неё. Ведомость отвечает «что у меня
          куплено», тариф — «оплачен ли кабинет, сколько израсходовано и что
          будет с данными». Второй вопрос задают реже, поэтому он ниже. */}
      {nav.linked && <PlanPanel />}
    </div>
  );
}

async function AgentRow({ agent }: { agent: NavAgent }) {
  const t = await getTranslations("agents");
  const locked = isLocked(agent.access);

  return (
    <li className="flex flex-wrap items-center gap-x-4 gap-y-3 px-4 py-4 sm:px-5">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {locked && (
            <Lock
              size={13}
              className="shrink-0 text-muted-foreground"
              aria-hidden="true"
            />
          )}
          <span className="font-medium">{t(`names.${agent.id}`)}</span>
          <Badge variant={TONE[agent.access]}>
            {t(`access.${agent.access}`)}
          </Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {t(`short.${agent.id}`)}
        </p>
        {agent.access === "expiring" && agent.daysLeft !== null && (
          /* Срок называется заранее, а не в день отключения: человек должен
             успеть продлить, а не обнаружить закрытый раздел. */
          <p className="mt-1 text-sm text-warn">
            {t("daysLeft", { days: agent.daysLeft })}
          </p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {agent.access === "locked" && agent.priceFrom !== null && (
          <span className="text-sm tabular-nums text-muted-foreground">
            {t("priceFrom", { price: agent.priceFrom })}
          </span>
        )}

        {agent.access === "unavailable" ? (
          /* Ни цены, ни кнопки. Оплата за непостроенного агента — это деньги
             за обещание, и никакая формулировка этого не исправляет. */
          <span className="text-sm text-muted-foreground">
            {t("comingSoon")}
          </span>
        ) : (
          <Link
            href={agent.href}
            className="inline-flex items-center gap-1.5 rounded-control border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            {agent.access === "locked" ? t("unlock") : t("open")}
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
        )}
      </div>
    </li>
  );
}
