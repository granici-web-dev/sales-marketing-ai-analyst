"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle } from "lucide-react";
import type { Warning } from "@/hooks/useInsights";

interface WarningCardProps {
  warning: Warning;
}

export function WarningCard({ warning }: WarningCardProps) {
  const t = useTranslations("insights");

  return (
    <Card className="border-yellow-200">
      <CardHeader className="pb-2 px-4 pt-4">
        <div className="flex items-center gap-2 flex-wrap">
          <Badge className="text-xs font-semibold border bg-yellow-100 text-yellow-800 border-yellow-200">
            <AlertTriangle size={12} className="mr-1" aria-hidden="true" />
            {t("warning.badge")}
          </Badge>
          <span className="font-medium text-sm">{warning.title}</span>
        </div>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-4">
        <p className="text-sm leading-relaxed text-foreground">
          {warning.description}
        </p>
      </CardContent>
    </Card>
  );
}
