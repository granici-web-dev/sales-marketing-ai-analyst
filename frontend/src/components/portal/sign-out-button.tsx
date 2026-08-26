"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { LogOut } from "lucide-react";

/**
 * Выход из учётной записи Davoq.
 *
 * Гасит сессию сервер, а не браузер: печенье с HttpOnly скриптам недоступно,
 * и это ровно то свойство, ради которого оно такое. Обработчик на сервере
 * гасит её ещё и в движке — иначе украденное печенье продолжало бы работать
 * после выхода.
 */
export function SignOutButton({ variant = "icon" }: { variant?: "icon" | "button" }) {
  const router = useRouter();
  const t = useTranslations("agents");

  const signOut = async () => {
    await fetch("/portal/session", { method: "DELETE" });
    router.refresh();
  };

  if (variant === "button") {
    return (
      <button
        type="button"
        onClick={signOut}
        className="inline-flex items-center gap-1.5 rounded-control border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
      >
        <LogOut size={14} aria-hidden="true" />
        {t("signOut")}
      </button>
    );
  }

  return (
    <button
      type="button"
      title={t("signOut")}
      aria-label={t("signOut")}
      onClick={signOut}
      className="flex size-8 shrink-0 items-center justify-center rounded-control text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <LogOut size={15} aria-hidden="true" />
    </button>
  );
}
