"use client";

/**
 * Включить агента — здесь, а не в другом приложении.
 *
 * Раньше на этом месте стояла кнопка, уводившая в панель движка: цену портал
 * знал, а чем платить — нет. Теперь знает: движок отдаёт вместе с агентом
 * самый дешёвый покупаемый тариф, в который тот входит.
 *
 * Оплата ведётся движком — там подписка, там Stripe, там вебхук, который
 * ставит тариф. Портал только начинает её и уводит на страницу оплаты.
 * Заводить второй расчёт значило бы иметь две правды о том, кто и за что
 * заплатил.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { engineApi, EngineRefused, EngineUnauthorized } from "@/lib/engine-client";
import type { UnlockPlan } from "@/lib/portal-agents";

type Period = "monthly" | "yearly";

interface CheckoutReply {
  url?: string;
  requested?: boolean;
  changed?: boolean;
}

export function UnlockPanel({ plan }: { plan: UnlockPlan }) {
  const t = useTranslations("agents.unlockPanel");
  const router = useRouter();
  const [period, setPeriod] = useState<Period>("monthly");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const price = period === "monthly" ? plan.priceEur : plan.priceEurYearly;

  async function subscribe() {
    setNotice(null);
    setBusy(true);
    try {
      const reply = await engineApi.send<CheckoutReply>("subscription/checkout", "POST", {
        plan: plan.id,
        period,
        // Оплата, начатая в портале, обязана и заканчиваться в портале.
        from: "portal",
      });

      if (reply.url) {
        window.location.href = reply.url;
        return;
      }
      if (reply.changed) {
        // Тариф ставит вебхук, а не мы: перерисовываем и показываем, что стало.
        router.refresh();
        setNotice({ kind: "ok", text: t("changed") });
        return;
      }
      // Оплата картой ещё не подключена — движок отправил заявку письмом.
      // Сказать это прямо честнее, чем изобразить успешную покупку.
      setNotice({ kind: "ok", text: t("requested") });
    } catch (error) {
      if (error instanceof EngineUnauthorized) {
        setNotice({ kind: "error", text: t("signedOut") });
      } else if (error instanceof EngineRefused) {
        setNotice({ kind: "error", text: error.message });
      } else {
        setNotice({ kind: "error", text: t("failed") });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <p className="text-sm">{t("lead", { plan: plan.name })}</p>

      {/* Годовая цена названа тем, что она есть: два месяца в подарок.
          «−17 %» требует считать, «2 luni gratuit» — нет. */}
      <div
        role="radiogroup"
        aria-label={t("period")}
        className="mt-4 inline-flex rounded-control border p-0.5"
      >
        {(["monthly", "yearly"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={period === value}
            onClick={() => setPeriod(value)}
            className={[
              "rounded-control px-3 py-1.5 text-sm transition-colors",
              period === value
                ? "bg-primary text-primary-foreground font-medium"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {t(value)}
          </button>
        ))}
      </div>

      <p className="mt-4 text-2xl font-semibold tabular-nums">
        {t(period === "monthly" ? "perMonth" : "perYear", { price })}
      </p>
      {period === "yearly" && (
        <p className="mt-1 text-sm text-ok">{t("yearlySaving")}</p>
      )}

      <button
        type="button"
        onClick={subscribe}
        disabled={busy}
        className="mt-4 inline-flex items-center gap-2 rounded-control bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-60"
      >
        {busy && <Loader2 size={15} className="animate-spin" aria-hidden="true" />}
        {t("subscribe")}
      </button>

      {notice && (
        <p
          role="status"
          className={[
            "mt-3 text-sm",
            notice.kind === "ok" ? "text-ok" : "text-danger",
          ].join(" ")}
        >
          {notice.text}
        </p>
      )}

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{t("note")}</p>
    </div>
  );
}
