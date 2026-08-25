"use client";

import { useTranslations } from "next-intl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CalendarCheck } from "lucide-react";

interface WeeklyActionPlanProps {
  items: string[];
}

export function WeeklyActionPlan({ items }: WeeklyActionPlanProps) {
  const t = useTranslations("insights");

  return (
    <Card className="border-blue-200">
      <CardHeader className="pb-2 px-4 pt-4">
        <div className="flex items-center gap-2">
          <CalendarCheck
            size={16}
            className="text-blue-700"
            aria-hidden="true"
          />
          <h3 className="font-semibold text-sm">{t("weeklyPlan.heading")}</h3>
        </div>
      </CardHeader>
      <CardContent className="pt-0 px-4 pb-4">
        <ol className="space-y-2 list-none">
          {items.map((item, idx) => (
            <li key={idx} className="flex gap-3 text-sm">
              <span
                className="flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-100 text-blue-800 text-xs font-semibold"
                aria-hidden="true"
              >
                {idx + 1}
              </span>
              <span className="leading-relaxed pt-0.5">{item}</span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
