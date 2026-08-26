"use client";

/**
 * Переписки виджета: что у бота спрашивали и что он отвечал.
 *
 * Экран нужен ради одного действия — поправить неверный ответ и утвердить
 * верный. Всё остальное здесь для того, чтобы такой ответ найти: фильтры,
 * поиск по тексту, отметки «оставил заявку» и «остались пробелы».
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslations, useFormatter } from "next-intl";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { engineApi, reportEngineError } from "@/lib/engine-client";

const PER = 25;

interface Conv {
  id: string;
  started_at: string;
  locale: string;
  message_count: number;
  has_lead: boolean;
  gap_count: number;
  first_question: string | null;
}

interface Turn {
  role: string;
  content: string;
  created_at: string;
  tool_calls: unknown;
}

interface Detail {
  messages: Turn[];
  lead: {
    name: string | null;
    email: string | null;
    phone: string | null;
    payload: Record<string, string>;
  } | null;
  gaps: Array<{ question: string; reason: string }>;
  fieldLabels?: Record<string, string>;
}

const EMPTY = {
  from: "",
  to: "",
  q: "",
  locale: "",
  hasLead: false,
  hasGap: false,
};

export function ConversationsScreen() {
  const t = useTranslations("agentScreens.conversationsScreen");
  const format = useFormatter();
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ rows: Conv[]; total: number } | null>(
    null,
  );
  const [error, setError] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [locales, setLocales] = useState<string[]>([]);

  /**
   * Ссылка из письма о заявке: `?conversation=<id>` открывает нужный разговор
   * сразу. Без неё письмо — тупик: прочитал и всё равно иди ищи руками среди
   * сотни переписок.
   *
   * Адрес читается один раз и тут же стирается. Иначе кнопка «назад к списку»
   * возвращала бы в тот же разговор, из которого человек только что вышел, —
   * та же причина, по которой так было сделано в панели движка.
   *
   * `window.location`, а не `useSearchParams`: тот требует границы Suspense
   * вокруг всего экрана ради одного чтения при монтировании.
   */
  useEffect(() => {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("conversation");
    if (!id) return;
    setOpen(id);
    url.searchParams.delete("conversation");
    window.history.replaceState(null, "", url.pathname + url.search);
  }, []);

  const when = (iso: string) =>
    format.dateTime(new Date(iso), { dateStyle: "short", timeStyle: "short" });

  const params = useMemo(() => {
    const p = new URLSearchParams();
    if (filters.from) p.set("from", filters.from);
    if (filters.to) p.set("to", filters.to);
    if (filters.q.trim()) p.set("q", filters.q.trim());
    if (filters.locale) p.set("locale", filters.locale);
    if (filters.hasLead) p.set("hasLead", "true");
    if (filters.hasGap) p.set("hasGap", "true");
    return p;
  }, [filters]);

  useEffect(() => {
    engineApi.get<{ locales: string[] }>("appearance").then(
      (a) => setLocales(a.locales),
      () => undefined,
    );
  }, []);

  // Запрос уходит на каждое нажатие клавиши, а отвечают они не по порядку:
  // без отбрасывания устаревших ответов в поле одно, а в таблице другое.
  const seq = useRef(0);

  useEffect(() => {
    const p = new URLSearchParams(params);
    p.set("limit", String(PER));
    p.set("offset", String(page * PER));
    setData(null);
    setError("");
    const mine = ++seq.current;
    engineApi.get<{ rows: Conv[]; total: number }>(`conversations?${p}`).then(
      (next) => {
        if (seq.current === mine) setData(next);
      },
      (err: unknown) => {
        // Ответ отставшего запроса не должен затирать текущий: `mine`
        // сторожит гонку, а показывать или перезагружать — решает помощник.
        reportEngineError(err, (text) => {
          if (seq.current === mine) setError(text);
        });
      },
    );
  }, [params, page]);

  if (open) {
    return (
      <ConversationDetail id={open} onBack={() => setOpen(null)} when={when} />
    );
  }

  const set = (patch: Partial<typeof EMPTY>) => {
    setFilters({ ...filters, ...patch });
    setPage(0);
  };

  const exportHref = (level: "conversation" | "message") => {
    const p = new URLSearchParams(params);
    p.set("level", level);
    return `/portal/engine/conversations/export?${p}`;
  };

  return (
    <div className="space-y-6">
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("filters")}</h2>

        <div className="mt-3 flex flex-wrap gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="f-from">{t("from")}</Label>
            <Input
              id="f-from"
              type="date"
              className="w-40"
              value={filters.from}
              onChange={(e) => set({ from: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="f-to">{t("to")}</Label>
            <Input
              id="f-to"
              type="date"
              className="w-40"
              value={filters.to}
              onChange={(e) => set({ to: e.target.value })}
            />
          </div>
          {locales.length > 1 && (
            <div className="space-y-1.5">
              <Label htmlFor="f-locale">{t("language")}</Label>
              <select
                id="f-locale"
                className="h-9 w-32 rounded-control border bg-card px-2 text-sm"
                value={filters.locale}
                onChange={(e) => set({ locale: e.target.value })}
              >
                <option value="">{t("allLanguages")}</option>
                {locales.map((l) => (
                  <option key={l} value={l}>
                    {l.toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        <div className="mt-3 space-y-1.5">
          <Label htmlFor="f-q">{t("search")}</Label>
          <Input
            id="f-q"
            placeholder={t("searchHint")}
            value={filters.q}
            onChange={(e) => set({ q: e.target.value })}
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={filters.hasLead}
              onChange={(e) => set({ hasLead: e.target.checked })}
            />
            {t("withLead")}
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-[var(--primary)]"
              checked={filters.hasGap}
              onChange={(e) => set({ hasGap: e.target.checked })}
            />
            {t("withGaps")}
          </label>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setFilters(EMPTY);
              setPage(0);
            }}
          >
            {t("reset")}
          </Button>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t pt-3">
          <span className="text-sm text-muted-foreground">
            {t("downloadWhatYouSee")}
          </span>
          <a href={exportHref("conversation")} download>
            <Button variant="outline" size="sm">
              <Download size={14} className="mr-1.5" aria-hidden="true" />
              {t("byConversation")}
            </Button>
          </a>
          <a href={exportHref("message")} download>
            <Button variant="outline" size="sm">
              <Download size={14} className="mr-1.5" aria-hidden="true" />
              {t("byMessage")}
            </Button>
          </a>
        </div>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {t("exportNote")}
        </p>
      </section>

      <section className="rounded-card border bg-card">
        <h2 className="border-b px-5 py-3 text-sm font-medium">
          {t("heading")}
          {data ? ` · ${data.total}` : ""}
        </h2>

        {error ? (
          <p role="alert" className="px-5 py-6 text-sm text-danger">
            {error}
          </p>
        ) : !data ? (
          <p className="flex items-center gap-2 px-5 py-6 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            {t("loading")}
          </p>
        ) : data.rows.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {data.rows.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setOpen(c.id)}
                  className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3 text-left transition-colors hover:bg-muted"
                >
                  <span className="w-32 shrink-0 text-sm text-muted-foreground tabular-nums">
                    {when(c.started_at)}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm">
                    {c.first_question ?? "—"}
                  </span>
                  {c.has_lead && <Badge variant="accent">{t("lead")}</Badge>}
                  {c.gap_count > 0 && (
                    <Badge variant="warn">{c.gap_count}</Badge>
                  )}
                  <span className="w-10 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                    {c.message_count}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {data && data.total > PER && (
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            {t("previous")}
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground">
            {page * PER + 1}–{Math.min((page + 1) * PER, data.total)} /{" "}
            {data.total}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={(page + 1) * PER >= data.total}
            onClick={() => setPage(page + 1)}
          >
            {t("next")}
          </Button>
        </div>
      )}
    </div>
  );
}

function ConversationDetail({
  id,
  onBack,
  when,
}: {
  id: string;
  onBack: () => void;
  when: (iso: string) => string;
}) {
  const t = useTranslations("agentScreens.conversationsScreen");
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  const [ask, setAsk] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [approved, setApproved] = useState<Set<number>>(new Set());

  const load = useCallback(() => {
    engineApi
      .get<Detail>(`conversations/${id}`)
      .then(setDetail, (err: unknown) => reportEngineError(err, setError));
  }, [id]);

  useEffect(() => load(), [load]);

  const approve = async (index: number) => {
    setBusy(true);
    setSaveError("");
    try {
      await engineApi.send("approved", "POST", {
        question: ask,
        answer: draft,
        conversationId: id,
      });
      setApproved(new Set(approved).add(index));
      setEditing(null);
    } catch (err) {
      reportEngineError(err, setSaveError);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <Button variant="ghost" size="sm" onClick={onBack}>
        <ArrowLeft size={14} className="mr-1.5" aria-hidden="true" />
        {t("backToList")}
      </Button>

      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : !detail ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={14} className="animate-spin" aria-hidden="true" />
          {t("loading")}
        </p>
      ) : (
        <>
          {detail.lead && (
            <section className="rounded-card border bg-card p-5">
              <h2 className="text-sm font-medium">{t("leadHeading")}</h2>
              <p className="mt-2 font-medium">
                {[detail.lead.name, detail.lead.email, detail.lead.phone]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              {Object.keys(detail.lead.payload ?? {}).length > 0 ? (
                <dl className="mt-3 space-y-1.5 text-sm">
                  {Object.entries(detail.lead.payload).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4">
                      <dt className="text-muted-foreground">
                        {detail.fieldLabels?.[k] ?? k}
                      </dt>
                      <dd className="text-right">{v}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  {t("contactOnly")}
                </p>
              )}
            </section>
          )}

          {detail.gaps.length > 0 && (
            <section className="rounded-card border bg-card p-5">
              <h2 className="text-sm font-medium">{t("gapsHeading")}</h2>
              <ul className="mt-2 space-y-1">
                {detail.gaps.map((g, i) => (
                  <li key={i} className="text-sm text-warn">
                    {g.question}
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section className="rounded-card border bg-card p-5">
            <h2 className="text-sm font-medium">{t("transcript")}</h2>
            <div className="mt-4 space-y-5">
              {detail.messages.map((turn, i) => {
                // Вопрос берётся из ближайшей реплики посетителя выше: правят
                // ответ, но утверждают пару — иначе искать его будет не по чему.
                const asked =
                  detail.messages
                    .slice(0, i)
                    .reverse()
                    .find((m) => m.role === "user")?.content ?? "";
                const editable = turn.role !== "user" && asked !== "";

                return (
                  <div
                    key={i}
                    className="border-l-2 pl-4"
                    style={{
                      borderColor:
                        turn.role === "user"
                          ? "var(--border)"
                          : "var(--primary)",
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs text-muted-foreground">
                        {turn.role === "user" ? t("visitor") : t("bot")} ·{" "}
                        {when(turn.created_at)}
                        {turn.tool_calls ? ` · ${t("usedTool")}` : ""}
                      </span>
                      {editable &&
                        editing !== i &&
                        (approved.has(i) ? (
                          <Badge variant="ok">{t("approvedStamp")}</Badge>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditing(i);
                              setDraft(turn.content);
                              setAsk(asked);
                              setSaveError("");
                            }}
                          >
                            {t("correct")}
                          </Button>
                        ))}
                    </div>

                    {editing === i ? (
                      <div className="mt-3 space-y-3">
                        {/* Вопрос правится вместе с ответом: посетитель мог
                            спросить «а в Клуж?» — утверждать ответ на такую
                            формулировку бессмысленно, по ней ничего не найдётся. */}
                        <div className="space-y-1.5">
                          <Label htmlFor={`ask-${i}`}>
                            {t("questionAnswered")}
                          </Label>
                          <Input
                            id={`ask-${i}`}
                            value={ask}
                            onChange={(e) => setAsk(e.target.value)}
                          />
                        </div>
                        <div className="space-y-1.5">
                          <Label htmlFor={`ans-${i}`}>
                            {t("answerApproved")}
                          </Label>
                          <Textarea
                            id={`ans-${i}`}
                            rows={5}
                            value={draft}
                            onChange={(e) => setDraft(e.target.value)}
                          />
                        </div>
                        <p className="text-xs leading-relaxed text-muted-foreground">
                          {t("approveNote")}
                        </p>
                        {saveError && (
                          <p role="alert" className="text-sm text-danger">
                            {saveError}
                          </p>
                        )}
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            disabled={busy || !ask.trim() || !draft.trim()}
                            onClick={() => void approve(i)}
                          >
                            {busy && (
                              <Loader2
                                size={13}
                                className="mr-1.5 animate-spin"
                                aria-hidden="true"
                              />
                            )}
                            {t("approve")}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setEditing(null)}
                          >
                            {t("cancel")}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-relaxed">
                        {turn.content}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
