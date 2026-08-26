"use client";

/**
 * Встройка виджета на сайт клиента.
 *
 * Три вещи по порядку, в котором их делают: взять код, проверить, что он
 * встал, и разрешить домены. Порядок не декоративный — проверка до встройки
 * ничего не найдёт, а домены без встройки не на чем проверить.
 */
import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Check, Copy, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { engineApi, reportEngineError } from "@/lib/engine-client";

interface InstallData {
  domains: string[];
  snippet: string;
}

interface VerifyResult {
  reachable: boolean;
  status: number | null;
  error: string | null;
  scriptFound: boolean;
  keyFound: boolean;
}

function Verdict({ ok, text }: { ok: boolean; text: string }) {
  return (
    <p className={["flex items-center gap-2 text-sm", ok ? "text-ok" : "text-danger"].join(" ")}>
      {ok ? <Check size={14} aria-hidden="true" /> : <X size={14} aria-hidden="true" />}
      {text}
    </p>
  );
}

export function InstallScreen() {
  const t = useTranslations("agentScreens.installScreen");
  const [data, setData] = useState<InstallData | null>(null);
  const [draft, setDraft] = useState("");
  const [copied, setCopied] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [checkUrl, setCheckUrl] = useState("");
  const [checking, setChecking] = useState(false);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [verifyError, setVerifyError] = useState("");

  useEffect(() => {
    engineApi.get<InstallData>("install").then((x) => {
      setData(x);
      setDraft(x.domains.join("\n"));
    }, () => undefined);
  }, []);

  if (!data) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  const save = async () => {
    setSaving(true);
    setNotice(null);
    const domains = draft.split("\n").map((s) => s.trim()).filter(Boolean);
    try {
      const next = await engineApi.send<InstallData>("install", "PUT", { domains });
      setDraft(next.domains.join("\n"));
      setNotice({ kind: "ok", text: t("saved") });
    } catch (err) {
      // Проглоченный отказ здесь означает мёртвый виджет при «сохранённых»
      // доменах — тихую поломку на сайте клиента.
      reportEngineError(err, (text) => setNotice({ kind: "error", text }));
    } finally {
      setSaving(false);
    }
  };

  const check = async () => {
    setChecking(true);
    setVerify(null);
    setVerifyError("");
    try {
      setVerify(await engineApi.send<VerifyResult>("install/verify", "POST", { url: checkUrl }));
    } catch (err) {
      reportEngineError(err, setVerifyError);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("snippetHeading")}</h2>
        <pre className="mt-3 overflow-x-auto rounded-control bg-muted p-3 font-mono text-xs leading-relaxed">
          {data.snippet}
        </pre>
        <div className="mt-3 flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void navigator.clipboard.writeText(data.snippet).then(() => setCopied(true))}
          >
            {copied ? (
              <Check size={14} className="mr-1.5" aria-hidden="true" />
            ) : (
              <Copy size={14} className="mr-1.5" aria-hidden="true" />
            )}
            {copied ? t("copied") : t("copy")}
          </Button>
          {/* Тег пишется как есть: сущности вида &lt; попадали бы на экран
              сырыми, и клиент видел абракадабру вместо закрывающего тега. */}
          <span className="text-sm text-muted-foreground">{t("beforeBody")}</span>
        </div>
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("verifyHeading")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("verifyLead")}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Input
            className="min-w-0 flex-1"
            placeholder="https://exemplu.ro/"
            aria-label={t("pageUrl")}
            value={checkUrl}
            onChange={(e) => setCheckUrl(e.target.value)}
          />
          <Button variant="outline" disabled={checking || !checkUrl.trim()} onClick={check}>
            {checking && <Loader2 size={14} className="mr-1.5 animate-spin" aria-hidden="true" />}
            {checking ? t("checking") : t("check")}
          </Button>
        </div>

        {verifyError && (
          <p role="alert" className="mt-3 text-sm text-danger">
            {verifyError}
          </p>
        )}

        {verify && (
          <div className="mt-3 space-y-1">
            <Verdict
              ok={verify.reachable}
              text={
                verify.reachable
                  ? t("reachable", { status: verify.status ?? 0 })
                  : t("unreachable", { error: verify.error ?? "" })
              }
            />
            {verify.reachable && (
              <>
                <Verdict
                  ok={verify.scriptFound}
                  text={verify.scriptFound ? t("scriptFound") : t("scriptMissing")}
                />
                <Verdict
                  ok={verify.keyFound}
                  text={verify.keyFound ? t("keyFound") : t("keyMissing")}
                />
              </>
            )}
          </div>
        )}
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("domainsHeading")}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">{t("domainsLead")}</p>
        <Textarea
          rows={4}
          className="mt-3 font-mono text-sm"
          aria-label={t("domainsHeading")}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            setNotice(null);
          }}
        />
        <div className="mt-3 flex items-center gap-3">
          <Button onClick={save} disabled={saving}>
            {saving && <Loader2 size={14} className="mr-2 animate-spin" aria-hidden="true" />}
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
      </section>
    </div>
  );
}
