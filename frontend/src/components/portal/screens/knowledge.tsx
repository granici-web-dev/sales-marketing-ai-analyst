"use client";

/**
 * База знаний чат-бота: из чего он отвечает.
 *
 * Обработка идёт в фоне, поэтому список сам обновляется — но только пока
 * что-то действительно обрабатывается. Опрос без условия крутился бы вечно
 * на экране, где ничего не меняется.
 */
import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, RotateCw, Trash2, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { engineApi, reportEngineError } from "@/lib/engine-client";

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

export function KnowledgeScreen() {
  const t = useTranslations("agentScreens.knowledgeScreen");
  const [docs, setDocs] = useState<Doc[] | null>(null);
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setDocs(await engineApi.get<Doc[]>("documents"));
    } catch (err) {
      reportEngineError(err, setError);
      setDocs([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // Обновляем, только пока что-то в работе.
  const pending = (docs ?? []).some((d) => d.status === "uploaded" || d.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => void load(), 2000);
    return () => clearInterval(timer);
  }, [pending, load]);

  const guard = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      await load();
    } catch (err) {
      reportEngineError(err, setError);
    } finally {
      setBusy(false);
    }
  };

  const upload = (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return guard(() => engineApi.upload("documents/upload", form));
  };

  // Материалы из Google Drive заводятся не здесь и удаляются не здесь.
  const site = (docs ?? []).filter((d) => !d.filename.startsWith("drive:"));

  return (
    <div className="max-w-3xl space-y-6">
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("addHeading")}</h2>

        <div className="mt-3 flex flex-wrap gap-2">
          <Input
            className="min-w-0 flex-1"
            placeholder="https://exemplu.ro/produse"
            value={url}
            aria-label={t("pageUrl")}
            onChange={(e) => setUrl(e.target.value)}
          />
          <Button
            disabled={busy || !url.trim()}
            onClick={() =>
              void guard(async () => {
                await engineApi.send("documents", "POST", { url });
                setUrl("");
              })
            }
          >
            {t("addPage")}
          </Button>
        </div>

        <label
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const file = e.dataTransfer.files[0];
            if (file) void upload(file);
          }}
          className="mt-3 flex cursor-pointer flex-col items-center gap-2 rounded-control border border-dashed bg-muted/40 px-4 py-6 text-center transition-colors hover:bg-muted"
        >
          <Upload size={18} className="text-muted-foreground" aria-hidden="true" />
          <span className="text-sm text-muted-foreground">{t("dropHint")}</span>
          <input
            type="file"
            accept=".docx,.odt,.pdf,.md,.txt,.html"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void upload(file);
            }}
          />
        </label>

        {busy && (
          <p className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            {t("sending")}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {error}
          </p>
        )}
      </section>

      <section className="rounded-card border bg-card">
        <h2 className="border-b px-5 py-3 text-sm font-medium">{t("listHeading")}</h2>

        {docs === null ? (
          <p className="flex items-center gap-2 px-5 py-6 text-sm text-muted-foreground">
            <Loader2 size={14} className="animate-spin" aria-hidden="true" />
            {t("loading")}
          </p>
        ) : site.length === 0 ? (
          <p className="px-5 py-6 text-sm text-muted-foreground">{t("empty")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {site.map((doc) => (
              <li key={doc.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm">{doc.filename}</p>
                  {doc.error_text && (
                    <p className="mt-0.5 text-sm text-danger">{doc.error_text}</p>
                  )}
                </div>
                <Badge variant={TONE[doc.status]}>{t(`status.${doc.status}`)}</Badge>
                <span className="w-16 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                  {doc.chunk_count}
                </span>
                <div className="flex shrink-0 gap-1">
                  {doc.status === "failed" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      title={t("retry")}
                      aria-label={t("retry")}
                      onClick={() => void guard(() => engineApi.send(`documents/${doc.id}/retry`, "POST"))}
                    >
                      <RotateCw size={15} aria-hidden="true" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    title={t("remove")}
                    aria-label={t("remove")}
                    onClick={() => void guard(() => engineApi.send(`documents/${doc.id}`, "DELETE"))}
                  >
                    <Trash2 size={15} aria-hidden="true" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
