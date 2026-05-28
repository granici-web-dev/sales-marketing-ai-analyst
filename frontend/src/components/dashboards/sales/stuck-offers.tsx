"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckCircle } from "lucide-react";
import { useTranslations } from "next-intl";
import type { StuckOffer } from "@/hooks/useSalesDashboard";

interface StuckOffersProps {
  stuckOffers: StuckOffer[];
}

function getDaysBadgeClass(days: number): string {
  if (days > 30) return "bg-red-100 text-red-800 border-red-200";
  if (days >= 14) return "bg-amber-100 text-amber-800 border-amber-200";
  return "bg-yellow-100 text-yellow-800 border-yellow-200";
}

export function StuckOffers({ stuckOffers }: StuckOffersProps) {
  const t = useTranslations("sales");

  if (!stuckOffers || stuckOffers.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-center">
        <CheckCircle
          size={32}
          className="text-green-500 mb-3"
          aria-hidden="true"
        />
        <p className="text-sm font-medium text-[#71717A]">
          {t("stuckOffers.noData")}
        </p>
        <p className="text-xs text-[#71717A] mt-1 max-w-xs">
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
          className="flex items-center justify-between p-3 rounded-lg border border-[hsl(240_6%_90%)] bg-white gap-4"
        >
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-medium text-[hsl(240_10%_4%)] truncate">
              #{offer.external_id}
            </span>
            <span className="text-xs text-[#71717A]">
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
