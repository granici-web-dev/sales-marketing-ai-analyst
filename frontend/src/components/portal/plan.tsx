"use client";

/**
 * Тариф: состояние оплаты, расход и пакеты.
 *
 * Не то же, что ведомость агентов на этой же странице. Ведомость отвечает
 * «что у меня куплено», а здесь — «оплачен ли сам кабинет, сколько израсходовано
 * и что будет с данными». Пакет включает агентов целиком; агента можно взять
 * и отдельно. Два вопроса, две части одного экрана.
 *
 * Переехало из панели движка последним. До этого расход, состояние оплаты и
 * дорога к счетам жили только там, и снести панель было нельзя, не отняв их.
 */
import { useCallback, useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { engineApi, reportEngineError } from "@/lib/engine-client";

/** Куда писать за пакетом, который ещё не продаётся. */
const ACCESS_EMAIL = "hello@assistwidget.eu";

interface PlanCard {
  id: string;
  name: string;
  priceEur: number;
  priceEurYearly: number;
  setupFeeEur: number;
  purchasable: boolean;
  highlights: string[];
  current: boolean;
}

interface SubscriptionData {
  plan: { id: string; name: string; priceEur: number; highlights: string[] };
  allPlans: PlanCard[];
  active: boolean;
  reason: string;
  daysLeft: number | null;
  currentPeriodEnd: string | null;
  usage: {
    messages: number;
    messagesCap: number;
    documents: number;
    documentsCap: number;
    chunks: number;
    chunksCap: number;
    bytes: number;
    bytesCap: number;
  };
  canManageBilling: boolean;
  retention: { conversationDays: number; canceledDays: number };
  canceledAt: string | null;
}

/**
 * Полоса расхода.
 *
 * Цвет меняется на девяноста процентах, а не на ста: сообщить, что лимит
 * ИСЧЕРПАН, — значит сообщить об этом, когда сделать уже ничего нельзя.
 */
function Meter({
  label,
  used,
  cap,
  format,
}: {
  label: string;
  used: number;
  cap: number;
  format?: (v: number) => string;
}) {
  const pct = cap > 0 ? Math.min(100, (used / cap) * 100) : 0;
  const show = format ?? ((v: number) => v.toLocaleString());
  const full = pct >= 90;

  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span>{label}</span>
        <span
          className={
            full
              ? "tabular-nums text-danger"
              : "tabular-nums text-muted-foreground"
          }
        >
          {show(used)} / {show(cap)}
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={full ? "h-full bg-danger" : "h-full bg-primary"}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function PlanPanel() {
  const t = useTranslations("plan");
  const format = useFormatter();

  const [data, setData] = useState<SubscriptionData | null>(null);
  const [busy, setBusy] = useState("");
  const [requested, setRequested] = useState("");
  const [yearly, setYearly] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await engineApi.get<SubscriptionData>("subscription"));
    } catch (err) {
      reportEngineError(err, setError);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const choose = async (planId: string) => {
    setBusy(planId);
    setError("");
    try {
      const answer = await engineApi.send<{
        url?: string;
        changed?: boolean;
        requested?: boolean;
      }>("subscription/checkout", "POST", {
        plan: planId,
        period: yearly ? "yearly" : "monthly",
      });
      // Нереализованный пакет не продаётся — заявка уходит человеку.
      if (answer.requested) {
        setRequested(planId);
        return;
      }
      if (answer.url) {
        location.href = answer.url;
        return;
      }
      await load();
    } catch (err) {
      reportEngineError(err, setError);
    } finally {
      setBusy("");
    }
  };

  const openBillingPortal = async () => {
    setBusy("portal");
    setError("");
    try {
      const { url } = await engineApi.send<{ url: string }>(
        "subscription/portal",
        "POST",
      );
      location.href = url;
    } catch (err) {
      reportEngineError(err, setError);
      setBusy("");
    }
  };

  if (data === null) {
    return error ? (
      <p role="alert" className="text-sm text-danger">
        {error}
      </p>
    ) : (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  const when = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "short" });
  const mb = (v: number) => `${Math.round(v / 1048576)} MB`;

  /* Состояние подписки словами, а не кодом. Читает директор по продажам,
     а не мы: «past_due» ему не говорит ничего, «карта не прошла» — говорит. */
  const state = ((): { text: string; tone: "ok" | "warn" | "danger" } => {
    switch (data.reason) {
      case "trial":
        return {
          tone: "ok",
          text:
            data.daysLeft !== null
              ? t("trialDaysLeft", { n: data.daysLeft })
              : t("trial"),
        };
      case "paid":
        return {
          tone: "ok",
          text: data.currentPeriodEnd
            ? t("activeUntil", { date: when(data.currentPeriodEnd) })
            : t("active"),
        };
      case "grace":
        return { tone: "warn", text: t("grace", { n: data.daysLeft ?? 0 }) };
      case "trial_expired":
        return { tone: "danger", text: t("trialExpired") };
      case "unpaid":
        return { tone: "danger", text: t("unpaid") };
      default:
        return { tone: "danger", text: t("canceled") };
    }
  })();

  return (
    <div className="space-y-6">
      <section className="rounded-card border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-medium">{data.plan.name}</h2>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {t("perMonth", { price: data.plan.priceEur })}
            </p>
          </div>
          <Badge variant={state.tone}>{state.text}</Badge>
        </div>

        {!data.active && (
          <p className="mt-3 text-sm text-danger">{t("stoppedAnswering")}</p>
        )}

        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          {data.plan.highlights.map((line) => (
            <li key={line}>· {line}</li>
          ))}
        </ul>

        <div className="mt-4 flex flex-wrap gap-2">
          {/* Оплата ТЕКУЩЕГО пакета, а не выбор тарифа: пробный период кончается
              ночью, и утром человек должен мочь заплатить сам, не дожидаясь нас.
              Тому, у кого подписка уже оформлена, эта кнопка не показывается —
              «Оплатить» рядом с «Активна» читается как просьба заплатить дважды.
              Ему нужна другая: карта и счета. */}
          {data.canManageBilling ? (
            <Button
              variant="ghost"
              disabled={busy !== ""}
              onClick={() => void openBillingPortal()}
            >
              {t("cardAndInvoices")}
            </Button>
          ) : (
            <Button
              disabled={busy !== ""}
              onClick={() => void choose(data.plan.id)}
            >
              {busy === data.plan.id ? t("sending") : t("paySubscription")}
            </Button>
          )}
        </div>

        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("usageHeading")}</h2>
        <div className="mt-4 space-y-3">
          <Meter
            label={t("messages")}
            used={data.usage.messages}
            cap={data.usage.messagesCap}
          />
          <Meter
            label={t("documents")}
            used={data.usage.documents}
            cap={data.usage.documentsCap}
          />
          <Meter
            label={t("chunks")}
            used={data.usage.chunks}
            cap={data.usage.chunksCap}
          />
          <Meter
            label={t("space")}
            used={data.usage.bytes}
            cap={data.usage.bytesCap}
            format={mb}
          />
        </div>
        <p className="mt-3 text-sm text-muted-foreground">
          {t("whenMessagesRunOut")}
        </p>
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("dataHeading")}</h2>
        <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
          <li>
            · {t("conversationsKept", { n: data.retention.conversationDays })}
          </li>
          <li>· {t("leadsStay")}</li>
          <li>· {t("afterCancel", { n: data.retention.canceledDays })}</li>
          <li>· {t("thenDeleted", { n: data.retention.canceledDays })}</li>
        </ul>
        {data.canceledAt && (
          <p className="mt-3 text-sm text-danger">
            {t("canceledOn", {
              date: when(data.canceledAt),
              n: data.retention.canceledDays,
            })}
          </p>
        )}
        <p className="mt-3 text-sm text-muted-foreground">
          {t("cancelViaPortal")}
        </p>
      </section>

      <section className="rounded-card border bg-card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-medium">{t("plansHeading")}</h2>
          <label className="flex items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={yearly}
              onChange={(e) => setYearly(e.currentTarget.checked)}
            />
            {t("yearlyToggle")}
          </label>
        </div>

        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          {data.allPlans.map((card) => (
            <li
              key={card.id}
              className={
                card.current
                  ? "rounded-card border border-primary/40 bg-primary/5 p-4"
                  : "rounded-card border p-4"
              }
            >
              <div className="flex items-baseline justify-between gap-2">
                <strong className="text-sm">{card.name}</strong>
                <span className="text-sm text-muted-foreground">
                  {/* Ноль означает «по запросу», а не «бесплатно». */}
                  {card.priceEur === 0
                    ? t("onRequest")
                    : yearly
                      ? t("perYear", { price: card.priceEurYearly })
                      : t("perMonth", { price: card.priceEur })}
                </span>
              </div>

              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {card.highlights.map((line) => (
                  <li key={line}>· {line}</li>
                ))}
              </ul>

              <div className="mt-3">
                {requested === card.id ? (
                  <Badge variant="ok">{t("requestSent")}</Badge>
                ) : card.current ? (
                  <Badge variant="ok">{t("yourPlan")}</Badge>
                ) : !card.purchasable ? (
                  /* Кнопки «оплатить» у нереализованного нет и быть не должно:
                     это была бы продажа долга, который отдаёт поддержка. */
                  <a
                    className="text-sm underline underline-offset-2"
                    href={`mailto:${ACCESS_EMAIL}?subject=${encodeURIComponent(
                      t("earlyAccessSubject", { plan: card.name }),
                    )}`}
                  >
                    {t("askEarlyAccess")}
                  </a>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={busy !== ""}
                    onClick={() => void choose(card.id)}
                  >
                    {busy === card.id ? t("sending") : t("choosePlan")}
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>

        {/* Сумма берётся из тарифа, а не из текста: цена, написанная словами
            в разметке, расходится с прайсом в первый же пересмотр. */}
        {data.allPlans
          .filter((card) => card.setupFeeEur > 0)
          .map((card) => (
            <p key={card.id} className="mt-3 text-sm text-muted-foreground">
              {t("setupFee", { plan: card.name, fee: card.setupFeeEur })}
            </p>
          ))}
      </section>
    </div>
  );
}
