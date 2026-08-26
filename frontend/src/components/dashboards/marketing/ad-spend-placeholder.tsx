"use client";

import { TrendingUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { Card, CardContent } from "@/components/ui/card";

export function AdSpendPlaceholder() {
  const t = useTranslations("marketing");

  return (
    <Card>
      <CardContent className="flex min-h-[200px] flex-col items-center justify-center p-6 text-center">
        <TrendingUp
          size={32}
          className="mb-3 text-muted-foreground"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-foreground">
          {t("adSpendTitle")}
        </p>
        <p className="mt-1 max-w-xs text-xs text-muted-foreground">
          {t("adSpendComingSoon")}
        </p>
      </CardContent>
    </Card>
  );
}
