"use client";

/**
 * Включить агента — поштучно, с вилкой и сроком.
 *
 * Раньше кнопка покупала ТАРИФ, в который агент входит, потому что другого
 * платежа в движке не было. Витрина же весь год продаёт агентов поштучно.
 * Клиент, взявший одного агента, получал счёт за пакет — расхождение, которое
 * замечает первый же покупатель.
 *
 * Цену здесь не считают. Скидки перемножаются (за количество и за год), и
 * вторая реализация этого правила разошлась бы с первой в первый же день.
 * Экран спрашивает движок и показывает, что скажут.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { engineApi, EngineRefused, EngineUnauthorized } from "@/lib/engine-client";

type Tier = "basic" | "pro";
type Period = "monthly" | "yearly";

interface Quote {
  lines: Array<{ agentId: string; tier: Tier; listMonthly: number; setup: number }>;
  period: Period;
  volumeDiscount: number;
  annualDiscount: number;
  listMonthly: number;
  recurring: number;
  setup: number;
  dueNow: number;
}

interface OrderReply {
  url?: string;
  requested?: boolean;
}

export function UnlockPanel({
  agentId,
  tiers,
}: {
  agentId: string;
  /** Вилки с ценами. Без обеих цен рядом выбор вилки — выбор вслепую. */
  tiers: Partial<Record<Tier, number>>;
}) {
  const t = useTranslations("agents.unlockPanel");
  const router = useRouter();
  const [tier, setTier] = useState<Tier>("basic");
  const [period, setPeriod] = useState<Period>("monthly");
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const available = (["basic", "pro"] as const).filter((k) => tiers[k] !== undefined);

  const refresh = useCallback(async () => {
    try {
      setQuote(
        await engineApi.send<Quote>("agents/quote", "POST", {
          items: [{ agentId, tier }],
          period,
        }),
      );
    } catch {
      // Цену не показываем вовсе, а не показываем прайсовую: прайсовая без
      // скидок выше настоящей, и человек решит, что ему считают дороже.
      setQuote(null);
    }
  }, [agentId, tier, period]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function order() {
    setNotice(null);
    setBusy(true);
    try {
      const reply = await engineApi.send<OrderReply>("agents/checkout", "POST", {
        items: [{ agentId, tier }],
        period,
      });

      if (reply.url) {
        window.location.href = reply.url;
        return;
      }
      // Оплата картой ещё не настроена — движок принял заказ письмом.
      // Сказать это прямо честнее, чем изобразить покупку.
      setNotice({ kind: "ok", text: t("requested") });
      router.refresh();
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
      {available.length > 1 && (
        <Choice
          label={t("tier")}
          value={tier}
          options={available.map((k) => ({
            value: k,
            label: `${t(`tiers.${k}`)} · ${t("perMonthShort", { price: tiers[k]! })}`,
          }))}
          onChange={(v) => setTier(v as Tier)}
        />
      )}

      <Choice
        label={t("period")}
        value={period}
        options={[
          { value: "monthly", label: t("monthly") },
          { value: "yearly", label: t("yearly") },
        ]}
        onChange={(v) => setPeriod(v as Period)}
      />

      <div className="mt-5 min-h-[104px]">
        {quote ? (
          <>
            <p className="text-2xl font-semibold tabular-nums">
              {t(period === "monthly" ? "perMonth" : "perYear", { price: quote.recurring })}
            </p>

            <dl className="mt-2 space-y-0.5 text-sm">
              {quote.volumeDiscount > 0 && (
                <Row
                  term={t("volumeDiscount", { percent: Math.round(quote.volumeDiscount * 100) })}
                  tone="ok"
                />
              )}
              {quote.annualDiscount > 0 && (
                <Row
                  term={t("annualDiscount", { percent: Math.round(quote.annualDiscount * 100) })}
                  tone="ok"
                />
              )}
              {quote.setup > 0 && <Row term={t("setup", { price: quote.setup })} />}
              <Row term={t("dueNow", { price: quote.dueNow })} strong />
            </dl>
          </>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            {t("counting")}
          </p>
        )}
      </div>

      <button
        type="button"
        onClick={order}
        disabled={busy || !quote}
        className="mt-4 inline-flex items-center gap-2 rounded-control bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-60"
      >
        {busy && <Loader2 size={15} className="animate-spin" aria-hidden="true" />}
        {t("subscribe")}
      </button>

      {notice && (
        <p
          role="status"
          className={["mt-3 text-sm", notice.kind === "ok" ? "text-ok" : "text-danger"].join(" ")}
        >
          {notice.text}
        </p>
      )}

      <p className="mt-3 text-xs leading-relaxed text-muted-foreground">{t("note")}</p>
    </div>
  );
}

function Choice({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-sm text-muted-foreground">{label}</p>
      <div role="radiogroup" aria-label={label} className="inline-flex rounded-control border p-0.5">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            onClick={() => onChange(option.value)}
            className={[
              "rounded-control px-3 py-1.5 text-sm transition-colors",
              value === option.value
                ? "bg-primary font-medium text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            ].join(" ")}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

function Row({ term, tone, strong }: { term: string; tone?: "ok"; strong?: boolean }) {
  return (
    <div
      className={[
        tone === "ok" ? "text-ok" : strong ? "font-medium" : "text-muted-foreground",
      ].join(" ")}
    >
      {term}
    </div>
  );
}
