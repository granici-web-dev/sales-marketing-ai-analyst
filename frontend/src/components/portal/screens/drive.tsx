"use client";

/**
 * Папка с материалами на Google Drive.
 *
 * Тот же список документов, что и на вкладке базы знаний, но с другой стороны:
 * там материалы добавляют по одному, здесь — кладут файл в папку, и бот
 * подхватывает его сам. Клиенту, у которого папка есть, вторая дорога обычно
 * не нужна вовсе, и в панели движка одну из вкладок ему прятали.
 */
import { useCallback, useEffect, useState } from "react";
import { useFormatter, useTranslations } from "next-intl";
import { Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { engineApi, EngineUnauthorized } from "@/lib/engine-client";

interface SyncResult {
  added: number;
  updated: number;
  removed: number;
  unchanged: number;
  errors: string[];
}

interface DriveState {
  connected: boolean;
  lastSyncAt?: string | null;
  everyMinutes?: number;
  closedRecently?: number;
  reopenedRecently?: number;
  lastResult?: SyncResult | null;
}

interface Doc {
  id: string;
  filename: string;
  status: "indexed" | "processing" | "uploaded" | "failed";
  chunk_count: number;
  error_text: string | null;
}

const TONE: Record<Doc["status"], "ok" | "warn" | "neutral" | "danger"> = {
  indexed: "ok",
  processing: "warn",
  uploaded: "warn",
  failed: "danger",
};

/** Сверка ставится в очередь, а не выполняется в ответе — ждём её признака. */
const SYNC_POLL_MS = 2000;
const SYNC_ATTEMPTS = 45;

export function DriveScreen() {
  const t = useTranslations("agentScreens.driveScreen");
  const format = useFormatter();

  const [state, setState] = useState<DriveState | null>(null);
  const [files, setFiles] = useState<Doc[]>([]);
  const [sitePages, setSitePages] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [stalled, setStalled] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (): Promise<DriveState | null> => {
    try {
      const [drive, all] = await Promise.all([
        engineApi.get<DriveState>("drive"),
        engineApi.get<Doc[]>("documents"),
      ]);
      setState(drive);
      setFiles(all.filter((d) => d.filename.startsWith("drive:")));
      setSitePages(all.filter((d) => !d.filename.startsWith("drive:")).length);
      return drive;
    } catch (err) {
      if (err instanceof EngineUnauthorized) {
        location.reload();
        return null;
      }
      setError((err as Error).message);
      setState({ connected: false });
      return null;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Индексация идёт в фоне. Опрос — только пока что-то действительно в работе:
  // иначе он крутился бы вечно на экране, где ничего не меняется.
  const pending = files.some(
    (d) => d.status === "uploaded" || d.status === "processing",
  );
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void load(), SYNC_POLL_MS);
    return () => clearInterval(timer);
  }, [pending, load]);

  /**
   * Ждём не фиксированные секунды, а признак того, что сверка прошла: время
   * последней сверки изменилось. Отсчёт по часам соврал бы «готово» при
   * остановленном обработчике — самая частая поломка на пилоте.
   */
  const sync = async () => {
    const before = state?.lastSyncAt ?? null;
    setSyncing(true);
    setStalled(false);
    setError("");
    try {
      await engineApi.send("drive/sync", "POST");
      for (let i = 0; i < SYNC_ATTEMPTS; i += 1) {
        await new Promise((r) => setTimeout(r, SYNC_POLL_MS));
        const fresh = await load();
        if (fresh && (fresh.lastSyncAt ?? null) !== before) return;
      }
      setStalled(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSyncing(false);
    }
  };

  if (state === null) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  if (!state.connected) {
    return (
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("heading")}</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("notConnected")}
        </p>
        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
      </section>
    );
  }

  const result = state.lastResult;
  const failed = files.filter((d) => d.status === "failed").length;

  return (
    <div className="space-y-6">
      <section className="rounded-card border bg-card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-sm font-medium">{t("heading")}</h2>
            {/* Числа подставляются в перевод, а не приклеиваются к его кускам:
                собранная из фрагментов фраза в другом языке не собирается. */}
            <p className="mt-1 text-sm text-muted-foreground">
              {t("lastCheck", {
                when: state.lastSyncAt
                  ? format.dateTime(new Date(state.lastSyncAt), {
                      dateStyle: "short",
                      timeStyle: "short",
                    })
                  : t("never"),
                every: state.everyMinutes ?? "—",
              })}
            </p>
            {result && (
              <p className="mt-1 text-sm text-muted-foreground">
                {t("counts", {
                  added: result.added,
                  updated: result.updated,
                  removed: result.removed,
                  same: result.unchanged,
                })}
                {result.errors.length > 0 && (
                  <span className="text-danger">
                    {" "}
                    · {t("errors", { n: result.errors.length })}
                  </span>
                )}
              </p>
            )}
          </div>
          <Button disabled={syncing} onClick={() => void sync()}>
            {syncing ? (
              <>
                <Loader2
                  size={14}
                  className="animate-spin"
                  aria-hidden="true"
                />
                {t("syncing")}
              </>
            ) : (
              <>
                <RefreshCw size={14} aria-hidden="true" />
                {t("syncNow")}
              </>
            )}
          </Button>
        </div>

        {stalled && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("stalled")}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
        {result?.errors.map((line, i) => (
          <p key={i} className="mt-1 text-sm text-danger">
            {line}
          </p>
        ))}

        <p className="mt-3 text-sm text-muted-foreground">{t("howItWorks")}</p>

        {sitePages > 0 && (
          /* Иначе директор решит, что бот знает только эти файлы, и начнёт
             перезаливать в папку то, что уже взято с сайта. */
          <p className="mt-1 text-sm text-muted-foreground">
            {t("alsoSitePages", { n: sitePages })}
          </p>
        )}
        {(state.closedRecently ?? 0) > 0 && (
          /* Ради этой строки всё и делалось: положил файл — увидел, что починил. */
          <p className="mt-1 text-sm text-ok">
            {t("gapsClosed", { n: state.closedRecently ?? 0 })}
          </p>
        )}
        {(state.reopenedRecently ?? 0) > 0 && (
          /* Обратная сторона: удаление файла должно быть видимым, иначе оно
             выглядит бесплатным, а список пробелов молча отрастает обратно. */
          <p className="mt-1 text-sm text-warn">
            {t("gapsReopened", { n: state.reopenedRecently ?? 0 })}
          </p>
        )}
      </section>

      <section className="rounded-card border bg-card">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h2 className="text-sm font-medium">{t("filesHeading")}</h2>
          {failed > 0 && (
            <Badge variant="danger">{t("unreadable", { n: failed })}</Badge>
          )}
        </div>

        {files.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">
            {t("empty")}
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {files.map((doc) => (
              <li
                key={doc.id}
                className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">
                    {doc.filename.replace(/^drive:/, "")}
                  </p>
                  {doc.error_text && (
                    <p className="mt-0.5 text-sm text-danger">
                      {doc.error_text}
                    </p>
                  )}
                </div>
                <Badge variant={TONE[doc.status]}>
                  {t(`status.${doc.status}`)}
                </Badge>
                <span className="w-16 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                  {doc.chunk_count}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
