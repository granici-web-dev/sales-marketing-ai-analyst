"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DayPicker, type DateRange } from "react-day-picker";
import { format, subDays, startOfMonth } from "date-fns";
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
import { formatDate, getDefaultDateRange } from "@/lib/formatters";
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

  const defaults = getDefaultDateRange();
  const currentFrom = searchParams.get("from") ?? defaults.from;
  const currentTo = searchParams.get("to") ?? defaults.to;

  const [open, setOpen] = useState(false);
  const [range, setRange] = useState<DateRange | undefined>({
    from: new Date(currentFrom),
    to: new Date(currentTo),
  });

  // Validate URL params (T-7-01 mitigation): fall back to defaults on invalid dates
  const validatedFrom = (() => {
    const d = new Date(currentFrom);
    return isNaN(d.getTime()) ? defaults.from : currentFrom;
  })();
  const validatedTo = (() => {
    const d = new Date(currentTo);
    return isNaN(d.getTime()) ? defaults.to : currentTo;
  })();

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
        !currentFrom && "text-muted-foreground",
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
