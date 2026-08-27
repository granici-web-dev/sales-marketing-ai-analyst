"use client";

import { Suspense, useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import { RefreshCw, Loader2, Lightbulb } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useInsightsToday,
  useInsightsByDate,
  useInsightsRefresh,
  InsightRefreshTimeout,
} from "@/hooks/useInsights";
import { InsightSummary } from "@/components/dashboards/insights/insight-summary";
import { ProblemCard } from "@/components/dashboards/insights/problem-card";
import { WarningCard } from "@/components/dashboards/insights/warning-card";
import { PositiveCard } from "@/components/dashboards/insights/positive-card";
import { WeeklyActionPlan } from "@/components/dashboards/insights/weekly-action-plan";
import { GenerationFailedBanner } from "@/components/dashboards/insights/generation-failed-banner";
import { FallbackAnomalyList } from "@/components/dashboards/insights/fallback-anomaly-list";
import { formatTimestamp } from "@/lib/formatters";

// ─── Countdown helper ───────────────────────────────────────────────────────

function formatCountdown(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ─── Main content component ─────────────────────────────────────────────────

function InsightsPageContent() {
  const t = useTranslations("insights");

  // INSI-01: today's insight (default view)
  const {
    data: insightsToday,
    isLoading: isTodayLoading,
    isError: isTodayError,
    refetch: refetchToday,
  } = useInsightsToday();

  // INSI-02: historical date picker
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // useInsightsByDate for historical navigation
  const {
    data: insightsByDate,
    isLoading: isByDateLoading,
    isError: isByDateError,
    refetch: refetchByDate,
  } = useInsightsByDate(selectedDate);

  // Derived active data — use historical when a date is selected
  const activeData = selectedDate !== null ? insightsByDate : insightsToday;
  const isLoading = selectedDate !== null ? isByDateLoading : isTodayLoading;
  const isError = selectedDate !== null ? isByDateError : isTodayError;
  const refetch = selectedDate !== null ? refetchByDate : refetchToday;

  // INSI-03: rate-limit state
  const [retryAfterSeconds, setRetryAfterSeconds] = useState<number | null>(
    null,
  );
  const [countdownDisplay, setCountdownDisplay] = useState<string>("");

  // W10 fix: useInsightsRefresh returns useMutation result
  const refreshMutation = useInsightsRefresh();

  // Watch mutation result for rate-limit response
  useEffect(() => {
    if (
      refreshMutation.data &&
      !refreshMutation.data.ok &&
      refreshMutation.data.retryAfterSeconds !== null
    ) {
      setRetryAfterSeconds(refreshMutation.data.retryAfterSeconds);
    }
  }, [refreshMutation.data]);

  // Countdown timer — counts down retryAfterSeconds to 0
  useEffect(() => {
    if (retryAfterSeconds === null) {
      setCountdownDisplay("");
      return;
    }
    setCountdownDisplay(formatCountdown(retryAfterSeconds));
    const interval = setInterval(() => {
      setRetryAfterSeconds((prev) => {
        if (prev === null || prev <= 1) {
          clearInterval(interval);
          setCountdownDisplay("");
          return null;
        }
        const next = prev - 1;
        setCountdownDisplay(formatCountdown(next));
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [retryAfterSeconds]);

  // T-7-15: validate date format before passing to hook
  function handleDateChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    if (!value) {
      setSelectedDate(null);
      return;
    }
    const parsed = new Date(value);
    if (isNaN(parsed.getTime())) {
      // Invalid date — ignore
      return;
    }
    setSelectedDate(value);
    // Clear rate-limit countdown when switching dates
    setRetryAfterSeconds(null);
  }

  function handleRefresh() {
    refreshMutation.mutate(selectedDate);
  }

  const isRateLimited = retryAfterSeconds !== null;
  const refreshDisabled = isRateLimited || refreshMutation.isPending;

  return (
    <div className="space-y-6">
      {/* ── Header row ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-semibold">{t("title")}</h1>
        <div className="flex gap-2 items-center flex-wrap">
          {/* INSI-02: historical date picker */}
          <Input
            type="date"
            className="w-auto"
            value={selectedDate ?? ""}
            onChange={handleDateChange}
            aria-label={t("datePicker")}
          />
          {/* Reset to today */}
          {selectedDate !== null && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedDate(null)}
            >
              {t("today")}
            </Button>
          )}
          {/* INSI-03: Reîmprospătează button */}
          <Button
            variant="default"
            disabled={refreshDisabled}
            onClick={handleRefresh}
          >
            {refreshMutation.isPending ? (
              <Loader2 size={16} className="mr-2 animate-spin" />
            ) : (
              <RefreshCw size={16} className="mr-2" />
            )}
            {isRateLimited
              ? t("refreshCountdown", { remaining: countdownDisplay })
              : t("refreshButton")}
          </Button>
        </div>
      </div>

      {/* Провал обновления. До этого страница читала только isPending:
          упавшая мутация просто гасила ожидание, и человек оставался
          с прежним текстом, не зная, что обновление не состоялось.
          Своя фраза, а не сообщение ошибки: там наша служебная строка
          по-английски. */}
      {refreshMutation.isError && (
        <p role="alert" className="text-sm text-destructive">
          {refreshMutation.error instanceof InsightRefreshTimeout
            ? t("refreshTimedOut")
            : t("refreshFailed")}
        </p>
      )}

      {/* ── Loading state ──────────────────────────────────────────────── */}
      {isLoading && (
        <div className="space-y-3">
          <Skeleton className="h-8 w-full mb-4" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
          <Skeleton className="h-20 w-full rounded-lg" />
        </div>
      )}

      {/* ── Error state ────────────────────────────────────────────────── */}
      {!isLoading && isError && (
        <div className="flex flex-col items-center gap-2 py-8">
          <p className="text-sm text-destructive">{t("loadFailed")}</p>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            {t("retry")}
          </Button>
        </div>
      )}

      {/* ── No data state (404 from history query) ─────────────────────── */}
      {!isLoading && !isError && selectedDate !== null && activeData === null && (
        <div className="flex flex-col items-center py-12 text-center">
          <Lightbulb
            size={32}
            className="text-muted-foreground mb-3"
            aria-hidden="true"
          />
          <p className="text-sm font-medium">{t("noInsight")}</p>
          <p className="text-sm text-muted-foreground mt-1">
            {t("noInsightDesc")}
          </p>
        </div>
      )}

      {/* ── Success path: insight data present ─────────────────────────── */}
      {!isLoading && !isError && activeData !== null && activeData !== undefined && (
        <div className="space-y-4">
          {/* INSI-05 Case: generation failed */}
          {activeData.generation_failed ? (
            <div className="space-y-4">
              {/* B6 fix: always show GenerationFailedBanner when generation_failed=true */}
              <GenerationFailedBanner />
              {/* FallbackAnomalyList handles Case A (fallback+problems) vs Case B (failed/empty) */}
              <FallbackAnomalyList
                problems={activeData.payload?.problems ?? null}
                status={activeData.status}
              />
            </div>
          ) : (
            <>
              {/* Normal success path */}
              {activeData.payload !== null && activeData.payload !== undefined && (
                <div className="space-y-6">
                  {/* INSI-01: AI summary paragraph */}
                  {/* B3 fix: pass payload.summary NOT payload.summary_ro */}
                  <InsightSummary
                    summary={activeData.payload.summary}
                    insightDate={activeData.date}
                  />

                  {/* Problems — critical issues with action plans */}
                  {activeData.payload.problems.length > 0 && (
                    <section className="space-y-3">
                      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        {t("sections.problems")}
                      </h2>
                      {activeData.payload.problems.map((p) => (
                        <ProblemCard key={p.id} problem={p} />
                      ))}
                    </section>
                  )}

                  {/* Warnings — weak signals worth monitoring */}
                  {activeData.payload.warnings.length > 0 && (
                    <section className="space-y-3">
                      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        {t("sections.warnings")}
                      </h2>
                      {activeData.payload.warnings.map((w, idx) => (
                        <WarningCard key={`warning-${idx}`} warning={w} />
                      ))}
                    </section>
                  )}

                  {/* Positives — what worked, scale or maintain */}
                  {activeData.payload.positives.length > 0 && (
                    <section className="space-y-3">
                      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                        {t("sections.positives")}
                      </h2>
                      {activeData.payload.positives.map((p, idx) => (
                        <PositiveCard key={`positive-${idx}`} positive={p} />
                      ))}
                    </section>
                  )}

                  {/* Weekly action plan — flat numbered list synthesized by Claude */}
                  {activeData.payload.weekly_action_plan.length > 0 && (
                    <WeeklyActionPlan
                      items={activeData.payload.weekly_action_plan}
                    />
                  )}

                  {/* Empty edge case — payload present but every section empty */}
                  {activeData.payload.problems.length === 0 &&
                    activeData.payload.warnings.length === 0 &&
                    activeData.payload.positives.length === 0 &&
                    activeData.payload.weekly_action_plan.length === 0 && (
                      <p className="text-sm text-muted-foreground italic">
                        {t("sections.emptyAll")}
                      </p>
                    )}
                </div>
              )}
            </>
          )}

          {/* INSI-06: Footer metadata — InsightEnvelope.date (not new Date()) */}
          <div className="pt-2 border-t">
            <p className="text-xs text-muted-foreground">
              {t("summary.dataFor")}{" "}
              {activeData.generated_at
                ? formatTimestamp(activeData.generated_at)
                : "—"}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Page export ────────────────────────────────────────────────────────────

export default function InsightsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full" />}>
      <InsightsPageContent />
    </Suspense>
  );
}
