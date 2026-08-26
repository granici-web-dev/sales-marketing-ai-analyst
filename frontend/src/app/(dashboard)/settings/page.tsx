import { getTranslations } from "next-intl/server";
import { ArrowUpRight } from "lucide-react";
import { PortalSignIn } from "@/components/portal/portal-sign-in";
import { SignOutButton } from "@/components/portal/sign-out-button";
import { engineBaseUrl } from "@/lib/engine";
import { loadPortalNav } from "@/lib/portal-nav.server";

/**
 * Учётная запись Davoq — то, что общее для всех агентов.
 *
 * Всё, что настраивается у КОНКРЕТНОГО агента, настраивается у него: марка,
 * домены, тексты бота живут в панели движка, и дублировать их здесь значило
 * бы завести второе место, где то же самое можно поменять по-другому.
 * Поэтому тут одна учётная запись и одна ссылка туда, где остальное.
 */
export default async function SettingsPage() {
  const t = await getTranslations("settings");
  const nav = await loadPortalNav();

  if (!nav.linked || !nav.account) {
    return (
      <div className="max-w-2xl space-y-6">
        <h1 className="text-xl font-semibold tracking-tight">{t("heading")}</h1>
        <PortalSignIn />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-xl font-semibold tracking-tight">{t("heading")}</h1>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("account")}</h2>
        <dl className="mt-3 space-y-2 text-sm">
          {nav.account.tenantName && (
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">{t("client")}</dt>
              <dd className="truncate font-medium">{nav.account.tenantName}</dd>
            </div>
          )}
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">{t("email")}</dt>
            <dd className="truncate">{nav.account.email}</dd>
          </div>
        </dl>
        <div className="mt-4">
          <SignOutButton variant="button" />
        </div>
      </section>

      <section className="rounded-card border bg-card p-5">
        <h2 className="text-sm font-medium">{t("elsewhere")}</h2>
        <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
          {t("elsewhereLead")}
        </p>
        <a
          href={`${engineBaseUrl()}/admin`}
          className="mt-4 inline-flex items-center gap-1.5 rounded-control border px-4 py-2 text-sm font-medium transition-colors hover:bg-muted"
        >
          {t("openPanel")}
          <ArrowUpRight size={14} aria-hidden="true" />
        </a>
      </section>
    </div>
  );
}
