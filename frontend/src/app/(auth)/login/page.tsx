import { getTranslations } from "next-intl/server";
import { PortalSignIn } from "@/components/portal/portal-sign-in";

/**
 * Вход — один на весь кабинет.
 *
 * Форма та же самая, что раньше стояла в разделе агентов: пока экраны
 * аналитика жили на собственном токене, дверей было две, и человек не понимал,
 * почему у одного кабинета два пароля. Теперь дверь одна, и открывает её
 * учётная запись Davoq.
 */
export default async function LoginPage() {
  const t = await getTranslations("auth");

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <p className="text-lg font-semibold tracking-tight">Davoq</p>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <PortalSignIn redirectTo="/" />
      </div>
    </div>
  );
}
