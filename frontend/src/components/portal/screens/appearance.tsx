"use client";

/**
 * Внешний вид виджета.
 *
 * Предпросмотр рисует движок и отдаёт готовой разметкой. Собрать его здесь
 * значило бы завести копию разметки виджета в другом репозитории — она
 * разошлась бы с оригиналом молча и показала клиенту не его бота.
 * Предупреждения о контрасте считает там же тот же аудит, что и при
 * сохранении: портал их только показывает.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { engineApi } from "@/lib/engine-client";

type DarkMode = "auto" | "light" | "dark";

interface Theme {
  primary: string;
  bg: string;
  text: string;
  userBubble: string;
  botBubble: string;
  darkMode: DarkMode;
}

interface Preset {
  id: string;
  name: string;
  theme: Theme;
}

interface Warning {
  field: string;
  message: string;
}

interface Appearance {
  botName: string;
  avatarUrl: string | null;
  position: string;
  theme: Theme;
  welcomeMessage: Record<string, string>;
  aiDisclosureText: Record<string, string>;
  warnings: Warning[];
  presets: Preset[];
  locales: string[];
}

const COLOR_FIELDS: Array<keyof Theme> = ["primary", "bg", "text", "userBubble", "botBubble"];

export function AppearanceScreen() {
  const t = useTranslations("agentScreens.appearanceScreen");
  const [data, setData] = useState<Appearance | null>(null);
  const [locale, setLocale] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ html: string; warnings: Warning[] } | null>(null);
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const loadError = useRef<string>("");

  useEffect(() => {
    engineApi
      .get<Appearance>("appearance")
      .then(setData)
      .catch((err: Error) => {
        loadError.current = err.message;
        setData(null);
      });
  }, []);

  const active = locale ?? data?.locales[0] ?? "en";

  const refreshPreview = useCallback(
    async (next: Appearance, forLocale: string) => {
      const reply = await engineApi.send<{ html: string; warnings: Warning[] }>(
        "appearance/preview",
        "POST",
        {
          theme: next.theme,
          botName: next.botName,
          locale: forLocale,
          welcome: next.welcomeMessage[forLocale] ?? "",
          disclosure: next.aiDisclosureText[forLocale] ?? "",
        },
      );
      setPreview(reply);
    },
    [],
  );

  // Предпросмотр обновляется с задержкой: ползунок цвета шлёт событие на
  // каждый оттенок, и запрос на каждое движение мыши — это сотни запросов.
  useEffect(() => {
    if (!data) return;
    const timer = setTimeout(() => void refreshPreview(data, active).catch(() => undefined), 250);
    return () => clearTimeout(timer);
  }, [data, active, refreshPreview]);

  if (!data) {
    return loadError.current ? (
      <p role="alert" className="text-sm text-danger">
        {loadError.current}
      </p>
    ) : (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 size={14} className="animate-spin" aria-hidden="true" />
        {t("loading")}
      </p>
    );
  }

  const patch = (next: Partial<Appearance>) => {
    setData({ ...data, ...next });
    setNotice(null);
  };

  const save = async () => {
    setSaving(true);
    setNotice(null);
    try {
      await engineApi.send("appearance", "PUT", {
        botName: data.botName,
        avatarUrl: data.avatarUrl,
        position: data.position,
        theme: data.theme,
        welcomeMessage: data.welcomeMessage,
        aiDisclosureText: data.aiDisclosureText,
      });
      setNotice({ kind: "ok", text: t("saved") });
    } catch (err) {
      // Проглоченный отказ здесь означает, что человек уходит с экрана
      // уверенный, что сохранил.
      setNotice({ kind: "error", text: (err as Error).message });
    } finally {
      setSaving(false);
    }
  };

  const warnings = preview?.warnings ?? data.warnings;

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
      <div className="space-y-6">
        <section className="rounded-card border bg-card p-5">
          <h2 className="text-sm font-medium">{t("presets")}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {data.presets.map((preset) => (
              <button
                key={preset.id}
                type="button"
                onClick={() => patch({ theme: preset.theme })}
                className="inline-flex items-center gap-2 rounded-control border px-3 py-1.5 text-sm transition-colors hover:bg-muted"
              >
                <span
                  className="size-3 rounded-full border"
                  style={{ background: preset.theme.primary }}
                  aria-hidden="true"
                />
                {preset.name}
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-card border bg-card p-5">
          <h2 className="text-sm font-medium">{t("colours")}</h2>
          <div className="mt-3 space-y-2.5">
            {COLOR_FIELDS.map((key) => (
              <div key={key} className="flex items-center justify-between gap-4">
                <Label htmlFor={`c-${key}`}>{t(`colour.${key}`)}</Label>
                <input
                  id={`c-${key}`}
                  type="color"
                  className="h-9 w-16 cursor-pointer rounded-control border bg-card p-1"
                  value={String(data.theme[key])}
                  onChange={(e) => patch({ theme: { ...data.theme, [key]: e.target.value } })}
                />
              </div>
            ))}
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="dark-mode">{t("darkMode")}</Label>
              <select
                id="dark-mode"
                className="h-9 rounded-control border bg-card px-2 text-sm"
                value={data.theme.darkMode}
                onChange={(e) =>
                  patch({ theme: { ...data.theme, darkMode: e.target.value as DarkMode } })
                }
              >
                <option value="auto">{t("dark.auto")}</option>
                <option value="light">{t("dark.light")}</option>
                <option value="dark">{t("dark.dark")}</option>
              </select>
            </div>
          </div>

          {warnings.length > 0 && (
            <div className="mt-4 space-y-1">
              {warnings.map((w) => (
                <p key={w.field} className="text-sm text-warn">
                  {w.message}
                </p>
              ))}
              <p className="text-xs leading-relaxed text-muted-foreground">{t("contrastNote")}</p>
            </div>
          )}
        </section>

        <section className="rounded-card border bg-card p-5">
          <h2 className="text-sm font-medium">{t("texts")}</h2>

          {data.locales.length > 1 && (
            <div className="mt-3 inline-flex rounded-control border p-0.5">
              {data.locales.map((l) => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setLocale(l)}
                  aria-pressed={active === l}
                  className={[
                    "rounded-control px-2.5 py-1 text-sm uppercase transition-colors",
                    active === l
                      ? "bg-primary font-medium text-primary-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  ].join(" ")}
                >
                  {l}
                </button>
              ))}
            </div>
          )}

          <div className="mt-3 space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="bot-name">{t("botName")}</Label>
              <Input
                id="bot-name"
                value={data.botName}
                onChange={(e) => patch({ botName: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="welcome">{t("welcome")}</Label>
              <Input
                id="welcome"
                value={data.welcomeMessage[active] ?? ""}
                onChange={(e) =>
                  patch({ welcomeMessage: { ...data.welcomeMessage, [active]: e.target.value } })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="disclosure">{t("disclosure")}</Label>
              <Input
                id="disclosure"
                value={data.aiDisclosureText[active] ?? ""}
                onChange={(e) =>
                  patch({
                    aiDisclosureText: { ...data.aiDisclosureText, [active]: e.target.value },
                  })
                }
              />
              <p className="text-xs leading-relaxed text-muted-foreground">
                {t("disclosureNote")}
              </p>
            </div>
          </div>
        </section>

        <div className="flex items-center gap-3">
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
      </div>

      <section className="rounded-card border bg-card p-4 lg:sticky lg:top-20 lg:self-start">
        <h2 className="mb-3 text-sm font-medium">{t("preview")}</h2>
        {preview ? (
          <iframe
            title={t("preview")}
            srcDoc={preview.html}
            className="h-[520px] w-full rounded-control border-0 bg-muted"
          />
        ) : (
          <div className="flex h-[520px] items-center justify-center rounded-control bg-muted">
            <Loader2 size={16} className="animate-spin text-muted-foreground" aria-hidden="true" />
          </div>
        )}
      </section>
    </div>
  );
}
