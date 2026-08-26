"use client";

/**
 * Акции конфигуратора.
 *
 * Подтверждение здесь — не техническая проверка «скрейпер правильно прочитал»,
 * а коммерческое решение: да, эту скидку ставить в оферты. Поэтому показаны
 * УСЛОВИЯ, а не то, откуда они взялись: сколько, на что и до какого числа.
 * Ошибку вида «акция на диваны применена к креслу» человек видит за секунду,
 * а машина не видит вовсе.
 *
 * До подтверждения скидка в оферты не идёт — они уходят без неё. Это сказано
 * на экране: молчаливое «ждёт подтверждения» читается как «уже работает».
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { engineApi, reportEngineError } from "@/lib/engine-client";

type PromoState = "pending" | "active" | "rejected" | "expired";

interface Promotion {
  id: string;
  source: "config" | "scrape";
  state: PromoState;
  /** Название по языкам клиента. */
  label: Record<string, string>;
  scope: "sitewide" | "models";
  modelIds: string[];
  discount: { percent?: number; bani?: number };
  validUntil: string | null;
  sourceUrl?: string;
}

const TONE: Record<PromoState, "ok" | "warn" | "neutral" | "danger"> = {
  pending: "warn",
  active: "ok",
  rejected: "neutral",
  expired: "neutral",
};

export function PromotionsScreen() {
  const t = useTranslations("agentScreens.promotionsScreen");
  const [items, setItems] = useState<Promotion[] | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setItems(await engineApi.get<Promotion[]>("promotions"));
    } catch (err) {
      reportEngineError(err, setError);
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (id: string, state: "active" | "rejected") => {
    setBusy(id);
    setError("");
    try {
      await engineApi.send(`promotions/${id}`, "POST", { state });
      await load();
    } catch (err) {
      reportEngineError(err, setError);
    } finally {
      setBusy("");
    }
  };

  if (items === null) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  // Ждущие решения — наверх: это единственное, что требует человека.
  const ordered = [
    ...items.filter((p) => p.state === "pending"),
    ...items.filter((p) => p.state !== "pending"),
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("heading")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("notAppliedUntilConfirmed")}
        </p>
        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
      </section>

      {ordered.length === 0 ? (
        <p className="rounded-card border bg-card px-5 py-6 text-sm text-muted-foreground">
          {t("empty")}
        </p>
      ) : (
        ordered.map((promo) => (
          <PromoCard
            key={promo.id}
            promo={promo}
            busy={busy === promo.id}
            onDecide={decide}
          />
        ))
      )}
    </div>
  );
}

function PromoCard({
  promo,
  busy,
  onDecide,
}: {
  promo: Promotion;
  busy: boolean;
  onDecide: (id: string, state: "active" | "rejected") => void;
}) {
  const t = useTranslations("agentScreens.promotionsScreen");

  /* Название приходит по языкам клиента; берём первое, потому что выбирать
     здесь не из чего — у клиента один рабочий язык на кабинет. */
  const label = Object.values(promo.label)[0] ?? "—";

  const amount =
    promo.discount.percent !== undefined
      ? `−${promo.discount.percent / 100}%`
      : `−${((promo.discount.bani ?? 0) / 100).toFixed(2)}`;

  return (
    <article className="rounded-card border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium">{label}</h3>
        <Badge variant={TONE[promo.state]}>{t(`state.${promo.state}`)}</Badge>
      </div>

      <p className="mt-2 text-sm">
        <span className="font-medium tabular-nums">{amount}</span>
        {" · "}
        {promo.scope === "sitewide"
          ? t("allProducts")
          : promo.modelIds.join(", ")}
        {" · "}
        {promo.validUntil
          ? t("until", { date: promo.validUntil })
          : t("noDeadline")}
      </p>

      <p className="mt-1 text-sm text-muted-foreground">
        {promo.source === "scrape" ? t("foundOnSite") : t("fromConfig")}
        {promo.sourceUrl && (
          <>
            {" · "}
            <a
              className="underline underline-offset-2"
              href={promo.sourceUrl}
              target="_blank"
              rel="noreferrer"
            >
              {t("source")}
            </a>
          </>
        )}
      </p>

      {promo.state !== "expired" && (
        <div className="mt-4 flex flex-wrap gap-2">
          {promo.state !== "active" && (
            <Button
              disabled={busy}
              onClick={() => onDecide(promo.id, "active")}
            >
              {t("confirm")}
            </Button>
          )}
          {promo.state === "pending" && (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => onDecide(promo.id, "rejected")}
            >
              {t("reject")}
            </Button>
          )}
          {promo.state === "active" && (
            <Button
              variant="ghost"
              disabled={busy}
              onClick={() => onDecide(promo.id, "rejected")}
            >
              {t("stop")}
            </Button>
          )}
        </div>
      )}
    </article>
  );
}
