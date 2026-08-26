"use client";

/**
 * Вход в портал, показанный на месте списка агентов.
 *
 * Не отдельная страница и не перенаправление намеренно. Раздел агентов
 * принадлежит учётной записи Davoq, а экраны аналитика пока живут на своей —
 * человек должен видеть, куда именно его просят войти и зачем, а не молча
 * оказаться на форме, похожей на ту, через которую он уже прошёл.
 *
 * Когда экраны переедут, эта панель станет единственным входом, а вторая
 * форма исчезнет.
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function PortalSignIn() {
  const t = useTranslations("agents.signIn");
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setError(null);
    setBusy(true);
    try {
      const response = await fetch("/portal/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: String(form.get("email") ?? ""),
          password: String(form.get("password") ?? ""),
        }),
      });
      if (response.ok) {
        // Печенье поставил сервер; список агентов рисуется на сервере, значит
        // страницу надо перерисовать, а не просто перерендерить у клиента.
        router.refresh();
        return;
      }
      setError(response.status === 401 ? t("invalid") : t("unavailable"));
    } catch {
      setError(t("unavailable"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-card border bg-card p-5 sm:p-6">
      <h2 className="font-medium">{t("title")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("lead")}</p>

      <form onSubmit={onSubmit} className="mt-5 max-w-sm space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor="portal-email">{t("email")}</Label>
          <Input id="portal-email" name="email" type="email" required autoComplete="email" />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="portal-password">{t("password")}</Label>
          <Input
            id="portal-password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
          />
        </div>

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}

        <Button type="submit" disabled={busy}>
          {busy && <Loader2 className="mr-2 size-4 animate-spin" aria-hidden="true" />}
          {t("submit")}
        </Button>
      </form>
    </div>
  );
}
