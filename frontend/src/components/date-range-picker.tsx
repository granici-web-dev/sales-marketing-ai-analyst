"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DayPicker, type DateRange } from "react-day-picker";
import { format, subDays, startOfMonth, startOfYear } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatDate } from "@/lib/formatters";
import { useUrlDateRange } from "@/hooks/useUrlDateRange";
import { cn } from "@/lib/utils";

// Detect hydration-safe viewport
function useIsMobile(): boolean {
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);
  return isMobile;
}

export function DateRangePicker() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const t = useTranslations("common");
  const isMobile = useIsMobile();

  // Single source of truth — uses window.location.search on mount, syncs to
  // searchParams on changes (same hook used by every dashboard page).
  const { from: validatedFrom, to: validatedTo } = useUrlDateRange();

  const [open, setOpen] = useState(false);
  const [range, setRange] = useState<DateRange | undefined>({
    from: new Date(validatedFrom),
    to: new Date(validatedTo),
  });

  // Sync internal range with URL params (browser back/forward, external router.push, refresh)
  useEffect(() => {
    setRange({ from: new Date(validatedFrom), to: new Date(validatedTo) });
  }, [validatedFrom, validatedTo]);

  function applyRange(r: DateRange | undefined) {
    if (!r?.from || !r?.to) return;
    const params = new URLSearchParams(searchParams.toString());
    // T-7-02 mitigation: format() returns YYYY-MM-DD strings from Date objects only
    params.set("from", format(r.from, "yyyy-MM-dd"));
    params.set("to", format(r.to, "yyyy-MM-dd"));
    router.push(`?${params.toString()}`);
    setOpen(false);
  }

  function applyPreset(from: Date, to: Date) {
    const r: DateRange = { from, to };
    setRange(r);
    applyRange(r);
  }

  const today = new Date();

  const presets = [
    {
      label: "Ultima săptămână",
      from: subDays(today, 6),
      to: today,
    },
    {
      label: "Ultima lună",
      from: subDays(today, 29),
      to: today,
    },
    {
      label: "Ultimele 90 zile",
      from: subDays(today, 89),
      to: today,
    },
    {
      label: "Luna curentă",
      from: startOfMonth(today),
      to: today,
    },
    {
      label: "Tot anul",
      from: startOfYear(today),
      to: today,
    },
  ];

  const triggerLabel = `${formatDate(validatedFrom)} – ${formatDate(validatedTo)}`;

  const calendarContent = (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap gap-2 px-1">
        {presets.map((preset) => (
          <Button
            key={preset.label}
            variant="outline"
            size="sm"
            className="min-h-[44px] text-xs"
            onClick={() => applyPreset(preset.from, preset.to)}
          >
            {preset.label}
          </Button>
        ))}
      </div>
      <DayPicker
        mode="range"
        selected={range}
        onSelect={(r) => {
          setRange(r);
          if (r?.from && r?.to) {
            applyRange(r);
          }
        }}
        numberOfMonths={isMobile ? 1 : 2}
        className="rounded-md"
      />
      {range?.from && !range?.to && (
        <div className="flex justify-end px-1">
          <Button
            size="sm"
            className="min-h-[44px]"
            onClick={() => applyRange(range)}
            disabled={!range?.from || !range?.to}
          >
            {t("apply")}
          </Button>
        </div>
      )}
    </div>
  );

  const triggerButton = (
    <Button
      variant="outline"
      className={cn(
        "min-h-[44px] gap-2 text-sm font-normal",
        !validatedFrom && "text-muted-foreground",
      )}
    >
      <CalendarIcon size={16} />
      {triggerLabel}
    </Button>
  );

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {isMobile ? (
        <>
          <Button
            variant="outline"
            className="min-h-[44px] gap-2 text-sm font-normal"
            onClick={() => setOpen(true)}
          >
            <CalendarIcon size={16} />
            {triggerLabel}
          </Button>
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetContent side="bottom" className="h-auto max-h-[90vh] overflow-y-auto">
              <SheetHeader className="mb-4">
                <SheetTitle>Selectează perioada</SheetTitle>
              </SheetHeader>
              {calendarContent}
            </SheetContent>
          </Sheet>
        </>
      ) : (
        <Popover open={open} onOpenChange={setOpen}>
          <PopoverTrigger asChild>{triggerButton}</PopoverTrigger>
          <PopoverContent className="w-auto p-3" align="end">
            {calendarContent}
          </PopoverContent>
        </Popover>
      )}

      {/* SALE-06 shape: disabled YoY toggle — Phase 9 feature placeholder */}
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <span>
              <Button
                variant="outline"
                disabled
                className="min-h-[44px] opacity-60 cursor-not-allowed"
              >
                Comparare An/An
              </Button>
            </span>
          </TooltipTrigger>
          <TooltipContent>
            <p>Disponibil în curând</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    </div>
  );
}
