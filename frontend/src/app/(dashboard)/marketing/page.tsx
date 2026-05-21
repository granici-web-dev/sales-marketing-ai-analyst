"use client";

import { useTranslations } from "next-intl";
import { TrendingUp } from "lucide-react";

export default function MarketingPage() {
  const t = useTranslations("placeholder");

  return (
    <div className="flex flex-col items-center justify-center min-h-[calc(100vh-56px-64px)]">
      <TrendingUp size={48} className="text-[#71717A] mb-4" aria-hidden="true" />
      <h1 className="text-xl font-semibold mb-2 text-[hsl(240_10%_4%)]">
        {t("comingSoon")}
      </h1>
      <p className="text-sm text-[#71717A] max-w-sm text-center">
        {t("marketing")}
      </p>
    </div>
  );
}
