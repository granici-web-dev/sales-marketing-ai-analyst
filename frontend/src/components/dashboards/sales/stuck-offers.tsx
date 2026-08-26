"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { StuckOffer } from "@/hooks/useSalesDashboard";

interface StuckOffersProps {
  stuckOffers: StuckOffer[];
}

/**
 * Тон плашки по числу дней простоя.
 *
 * Уровня было три — красный, янтарный, жёлтый, — и третий убран.
 * Не ради токенов: жёлтый рядом с двумя тревожными читается как третья
 * степень тревоги, хотя означает ровно обратное — «эта оферта застряла
 * меньше двух недель, ею можно заняться не сегодня». Список и так
 * отсортирован, и порядок несёт эту разницу лучше цвета.
 */
function getDaysBadgeClass(days: number): string {
  if (days > 30) return "bg-danger/12 text-danger border-danger/25";
  if (days >= 14) return "bg-warn/12 text-warn border-warn/25";
  return "bg-muted text-muted-foreground border-border";
}

export function StuckOffers({ stuckOffers }: StuckOffersProps) {
  const t = useTranslations("sales");

  if (!stuckOffers || stuckOffers.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <CheckCircle
          size={32}
          className="text-ok mb-3"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-muted-foreground">
          {t("stuckOffers.noData")}
        </p>
        <p className="text-xs text-muted-foreground mt-1 max-w-xs">
          {t("stuckOffers.noDataDesc")}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {stuckOffers.map((offer) => (
        <div
          key={offer.external_id}
          className="flex items-center justify-between p-3 rounded-lg border border-border bg-card gap-4"
        >
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-foreground truncate">
              #{offer.external_id}
            </span>
            <span className="text-xs text-muted-foreground">
              {offer.salesperson_name ?? "—"}
            </span>
          </div>
          <Badge
            variant="outline"
            className={`shrink-0 ${getDaysBadgeClass(offer.days_stuck)}`}
          >
            {offer.days_stuck}{" "}
            {offer.days_stuck === 1 ? "zi" : "zile"}
          </Badge>
        </div>
      ))}
    </div>
  );
}
