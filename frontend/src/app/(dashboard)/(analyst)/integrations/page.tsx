"use client";

import { useTranslations } from "next-intl";
import { Plug } from "lucide-react";

export default function IntegrationsPage() {
  const t = useTranslations("placeholder");

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-56px-64px)]">
      <Plug size={48} className="text-muted-foreground mb-4" aria-hidden="true" />
      <h1 className="text-xl font-semibold mb-2 text-foreground">
        {t("comingSoon")}
      </h1>
      <p className="text-sm text-muted-foreground max-w-sm text-center">
        {t("integrations")}
      </p>
    </div>
  );
}
