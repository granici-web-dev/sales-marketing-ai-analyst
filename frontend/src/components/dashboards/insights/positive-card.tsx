"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2 } from "lucide-react";
import type { Positive } from "@/hooks/useInsights";

interface PositiveCardProps {
  positive: Positive;
}

export function PositiveCard({ positive }: PositiveCardProps) {
  const t = useTranslations("insights");

  return (
    <Card className="border-ok/30">
      <CardHeader className="pb-2 px-4 pt-4">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="ok">
            <CheckCircle2 size={12} className="mr-1" aria-hidden="true" />
            {t("positive.badge")}
          </Badge>
          <span className="font-medium text-sm">{positive.title}</span>
        </div>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-4 space-y-2">
        <p className="text-sm leading-relaxed text-foreground">
          {positive.description}
        </p>
        {positive.recommendation && (
          <p className="text-xs text-muted-foreground italic">
            <span className="font-semibold not-italic uppercase tracking-wide text-muted-foreground">
              {t("positive.recommendation")}:{" "}
            </span>
            {positive.recommendation}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
