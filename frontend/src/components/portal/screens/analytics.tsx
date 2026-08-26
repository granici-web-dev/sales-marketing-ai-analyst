"use client";

/**
 * Аналитика чат-бота.
 *
 * Разделы стоят в порядке «что делать дальше», а не «что у нас есть»:
 * расход — чтобы знать запас; вопросы без ответа — самый короткий путь
 * сделать бота лучше; утверждённые ответы — то, что уже поправили;
 * воронка конфигуратора и заявки — то, ради чего всё это работает.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslations, useFormatter } from "next-intl";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Loader2, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { engineApi, reportEngineError } from "@/lib/engine-client";

interface Lead {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  note: string | null;
  created_at: string;
  notified_at: string | null;
  notify_error: string | null;
  product: string;
  payload: { summary?: string[]; totalFormatted?: string } | null;
  offer_id: string | null;
  offer_number: string | null;
  has_pdf: boolean;
}

interface AnalyticsData {
  usage: Array<{ date: string; messages: number }>;
  unanswered: Array<{ question: string; times: number; last_seen: string }>;
  closed?: Array<{ question: string; times: number; resolved_at: string; answer: string | null }>;
  leads: Lead[];
  notifyEmail?: string;
  quota: { plan: string; cap: number | null; usedThisMonth: number };
}

interface Approved {
  id: string;
  question: string;
  answer: string;
  updated_at: string;
}

interface FunnelData {
  days: number;
  opened: number;
  priceShown: number;
  offers: number;
  steps: Array<{ stepId: string; title: string; views: number; next: number }>;
}

export function AnalyticsScreen() {
  const t = useTranslations("agentScreens.analyticsScreen");
  const format = useFormatter();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [approved, setApproved] = useState<Approved[]>([]);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [error, setError] = useState("");

  const day = (iso: string) => format.dateTime(new Date(iso), { dateStyle: "short" });

  const loadApproved = useCallback(
    () => engineApi.get<Approved[]>("approved").then(setApproved, () => setApproved([])),
    [],
  );

  useEffect(() => {
    engineApi
      .get<AnalyticsData>("insights")
      .then(setData, (err: unknown) => reportEngineError(err, setError));
    void loadApproved();
    // Конфигуратора нет — воронки тоже. Пустая воронка у чат-бота выглядела бы
    // поломкой, а не отсутствием продукта.
    engineApi.get<FunnelData | null>("funnel").then(setFunnel, () => setFunnel(null));
  }, [loadApproved]);

  const total = useMemo(
    () => (data?.usage ?? []).reduce((sum, row) => sum + row.messages, 0),
    [data],
  );

  if (error) {
    return (
      <p role="alert" className="text-sm text-danger">
        {error}
      </p>
    );
  }
  if (!data) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("usage")}</h2>
        <div className="mt-3 flex flex-wrap gap-8">
          <Figure value={data.quota.usedThisMonth} label={t("thisMonth")} />
          {data.quota.cap !== null && <Figure value={data.quota.cap} label={t("includedInPlan")} />}
          <Figure value={total} label={t("last30")} />
        </div>

        {data.usage.length > 1 && (
          <div className="mt-5 h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.usage} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="usage-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.28} />
                    <stop offset="100%" stopColor="var(--primary)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="date"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 11, fill: "var(--muted-fg)" }}
                  // Подписаны только края: тридцать дат подряд не читает никто.
                  ticks={[data.usage[0]!.date, data.usage[data.usage.length - 1]!.date]}
                  tickFormatter={day}
                />
                <YAxis hide />
                <Tooltip
                  contentStyle={{
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    fontSize: 12,
                  }}
                  labelFormatter={(value) => day(String(value))}
                  formatter={(value) => [value, t("messages")]}
                />
                <Area
                  type="monotone"
                  dataKey="messages"
                  stroke="var(--primary)"
                  strokeWidth={2}
                  fill="url(#usage-fill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("unanswered")}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t("unansweredLead")}</p>
        {data.unanswered.length === 0 ? (
          <p className="mt-3 text-sm text-muted-foreground">{t("unansweredEmpty")}</p>
        ) : (
          <ul className="mt-3 divide-y divide-border">
            {data.unanswered.map((u, i) => (
              <li key={i} className="flex items-center gap-4 py-2">
                <span className="min-w-0 flex-1 text-sm">{u.question}</span>
                <span className="shrink-0 text-sm tabular-nums text-muted-foreground">
                  {u.times}
                </span>
                <span className="w-24 shrink-0 text-right text-sm text-muted-foreground">
                  {day(u.last_seen)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Поле может не прийти от сервера более старой сборки. Отсутствующий
          раздел — это отсутствующий раздел, а не пустой экран. */}
      {(data.closed ?? []).length > 0 && (
        <section className="rounded-card border bg-card p-5">
          <h2 className="text-sm font-medium">{t("closed")}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t("closedLead")}</p>
          <div className="mt-3 space-y-4">
            {(data.closed ?? []).map((c, i) => (
              <div key={i}>
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm font-medium">{c.question}</p>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {day(c.resolved_at)}
                  </span>
                </div>
                {c.answer && (
                  <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{c.answer}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}

      {approved.length > 0 && (
        <section className="rounded-card border bg-card p-5">
          <h2 className="text-sm font-medium">{t("approved")}</h2>
          <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t("approvedLead")}</p>
          <div className="mt-3 space-y-4">
            {approved.map((a) => (
              <div key={a.id}>
                <div className="flex items-start justify-between gap-4">
                  <p className="text-sm font-medium">{a.question}</p>
                  <span className="flex shrink-0 items-center gap-2">
                    <span className="text-xs text-muted-foreground">{day(a.updated_at)}</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      title={t("remove")}
                      aria-label={t("remove")}
                      onClick={() =>
                        void engineApi.send(`approved/${a.id}`, "DELETE").then(loadApproved)
                      }
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </Button>
                  </span>
                </div>
                <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{a.answer}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {funnel && <Funnel data={funnel} />}

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("leads")}</h2>
        <NotifyEmail initial={data.notifyEmail ?? ""} />

        {data.leads.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">{t("leadsEmpty")}</p>
        ) : (
          <ul className="mt-4 divide-y divide-border">
            {data.leads.map((lead) => (
              <li key={lead.id} className="py-3">
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="text-sm text-muted-foreground tabular-nums">
                    {day(lead.created_at)}
                  </span>
                  <span className="font-medium">{lead.name ?? "—"}</span>
                  {lead.product === "configurator" && (
                    <Badge variant="neutral">{t("fromConfigurator")}</Badge>
                  )}
                  {/* Молчаливая ошибка отправки — это заявка, о которой никто
                      не узнал. Директор должен узнать об этом здесь, а не по
                      отсутствию звонков. */}
                  {lead.notified_at ? (
                    <Badge variant="ok">{t("sent")}</Badge>
                  ) : lead.notify_error ? (
                    <Badge variant="danger" title={lead.notify_error}>
                      {t("notSent")}
                    </Badge>
                  ) : null}
                </div>

                <p className="mt-0.5 text-sm text-muted-foreground">
                  {[lead.email, lead.phone].filter(Boolean).join(" · ")}
                </p>

                {lead.note && <p className="mt-1 text-sm">{lead.note}</p>}

                {lead.offer_number && (
                  <p className="mt-1 text-sm">
                    <span className="font-medium">№ {lead.offer_number}</span>
                    {lead.payload?.totalFormatted && ` · ${lead.payload.totalFormatted}`}
                    {lead.has_pdf && lead.offer_id && (
                      <>
                        {" · "}
                        <a
                          href={`/portal/engine/offers/${lead.offer_id}/pdf`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-primary hover:underline"
                        >
                          PDF
                        </a>
                      </>
                    )}
                  </p>
                )}

                {(lead.payload?.summary ?? []).length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-sm text-muted-foreground">
                    {lead.payload!.summary!.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function Figure({ value, label }: { value: number; label: string }) {
  return (
    <p className="flex flex-col">
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
    </p>
  );
}

function Funnel({ data }: { data: FunnelData }) {
  const t = useTranslations("agentScreens.analyticsScreen");
  const max = Math.max(data.opened, ...data.steps.map((s) => s.views), 1);

  const rows = [
    { label: t("opened"), value: data.opened, lost: 0, strong: false },
    ...data.steps.map((s) => ({
      label: s.title,
      value: s.views,
      lost: s.views > 0 ? s.views - s.next : 0,
      strong: false,
    })),
    { label: t("priceShown"), value: data.priceShown, lost: 0, strong: false },
    { label: t("offers"), value: data.offers, lost: 0, strong: true },
  ];

  return (
    <section className="rounded-card border bg-card p-5">
      <h2 className="text-sm font-medium">{t("funnel")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("lastDays", { days: data.days })}</p>

      <div className="mt-4 space-y-1.5">
        {rows.map((row, i) => (
          <div key={i} className="flex items-center gap-3">
            <span
              className={[
                "w-40 shrink-0 truncate text-sm",
                row.strong ? "font-medium" : "text-muted-foreground",
              ].join(" ")}
            >
              {row.label}
            </span>
            <span className="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
              <span
                className={["block h-full rounded-full", row.strong ? "bg-accent-strong" : "bg-primary"].join(" ")}
                style={{ width: `${(row.value / max) * 100}%` }}
              />
            </span>
            <span className="w-12 shrink-0 text-right text-sm tabular-nums">{row.value}</span>
            {/* Потери показаны рядом со ступенью, а не отдельной таблицей:
                вопрос «где отваливаются» задают, глядя на саму ступень. */}
            <span className="w-12 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
              {row.lost > 0 ? `−${row.lost}` : ""}
            </span>
          </div>
        ))}
      </div>

      {data.opened === 0 && (
        <p className="mt-3 text-sm text-muted-foreground">{t("funnelEmpty")}</p>
      )}
    </section>
  );
}

/**
 * Куда слать заявки. Поле стоит здесь, а не в настройках: директор смотрит
 * на список заявок, и вопрос «а мне об этом сообщат?» возникает именно тут.
 */
function NotifyEmail({ initial }: { initial: string }) {
  const t = useTranslations("agentScreens.analyticsScreen");
  const [value, setValue] = useState(initial);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  const save = async () => {
    setNotice(null);
    try {
      const reply = await engineApi.send<{ error?: string }>("lead-notify", "PUT", { email: value });
      setNotice(
        reply.error
          ? { kind: "error", text: reply.error }
          : { kind: "ok", text: t("saved") },
      );
    } catch (err) {
      reportEngineError(err, (text) => setNotice({ kind: "error", text }));
    }
  };

  return (
    <div className="mt-3 space-y-1.5">
      <Label htmlFor="notify-email">{t("notifyTo")}</Label>
      <div className="flex flex-wrap items-center gap-2">
        <Input
          id="notify-email"
          type="email"
          placeholder="vanzari@exemplu.ro"
          className="min-w-[200px] max-w-[420px] flex-1"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setNotice(null);
          }}
        />
        <Button size="sm" onClick={save}>
          {t("save")}
        </Button>
        {notice && (
          <span
            role="status"
            className={["text-sm", notice.kind === "ok" ? "text-ok" : "text-danger"].join(" ")}
          >
            {notice.text}
          </span>
        )}
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{t("notifyNote")}</p>
    </div>
  );
}
