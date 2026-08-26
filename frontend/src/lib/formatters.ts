/**
 * Shared formatting utilities for the Sales & Marketing AI Analyst dashboard.
 * All monetary values use Romanian locale (dot-thousands, comma-decimal, RON suffix).
 * All date values use DD.MM.YYYY format in Europe/Bucharest timezone.
 */

import { parseISO } from "date-fns";

/**
 * Format a monetary value as Romanian RON currency.
 * @param value - The value to format (string, number, null, or undefined)
 * @param compact - If true, use 0 decimal places
 * @returns Formatted string like "85.000,00 RON" or "N/A" for null/undefined
 */
export function formatRON(
  value: string | number | null | undefined,
  compact = false,
): string {
  if (value === null || value === undefined) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";
  return new Intl.NumberFormat("ro-RO", {
    style: "currency",
    currency: "RON",
    maximumFractionDigits: compact ? 0 : 2,
  }).format(num);
}

/**
 * Format a decimal fraction as a Romanian percentage.
 * @param value - Decimal value (e.g., 0.285 for 28.5%)
 * @returns Formatted string like "28,5%" or "N/A" for null/undefined
 */
export function formatPct(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "N/A";
  return new Intl.NumberFormat("ro-RO", {
    style: "percent",
    maximumFractionDigits: 1,
  }).format(num);
}

/**
 * Format a date as DD.MM.YYYY.
 * @param dateStr - ISO date string, Date object, null, or undefined
 * @returns Formatted string like "28.05.2026" or "" for null/undefined
 */
export function formatDate(
  dateStr: string | Date | null | undefined,
): string {
  if (!dateStr) return "";
  // parseISO, а не new Date: строку «2026-05-28» конструктор читает как
  // полночь UTC, и западнее нулевого меридиана подпись показывала бы
  // предыдущий день — то самое число, которое клиент и читает под кнопкой
  // выбора периода. В Бухаресте (UTC+2/+3) расхождения нет, поэтому и жило.
  // Полные отметки времени со смещением parseISO разбирает так же верно.
  const d = typeof dateStr === "string" ? parseISO(dateStr) : dateStr;
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(d);
}

/**
 * Format a datetime as DD.MM.YYYY HH:MM in Europe/Bucharest timezone.
 * @param dateStr - ISO datetime string, Date object, null, or undefined
 * @returns Formatted string like "28.05.2026 08:30" or "" for null/undefined
 */
export function formatTimestamp(
  dateStr: string | Date | null | undefined,
): string {
  if (!dateStr) return "";
  // parseISO, а не new Date: строку «2026-05-28» конструктор читает как
  // полночь UTC, и западнее нулевого меридиана подпись показывала бы
  // предыдущий день — то самое число, которое клиент и читает под кнопкой
  // выбора периода. В Бухаресте (UTC+2/+3) расхождения нет, поэтому и жило.
  // Полные отметки времени со смещением parseISO разбирает так же верно.
  const d = typeof dateStr === "string" ? parseISO(dateStr) : dateStr;
  return new Intl.DateTimeFormat("ro-RO", {
    timeZone: "Europe/Bucharest",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

/**
 * Format a duration in minutes as a human-readable Romanian string.
 * @param minutes - Duration in minutes (integer), null, or undefined
 * @returns Formatted string like "2h 30min", "45min", "1h", or "N/A"
 */
export function formatDuration(
  minutes: number | null | undefined,
): string {
  if (minutes === null || minutes === undefined) return "N/A";
  if (minutes < 60) return `${minutes}min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h ${m}min` : `${h}h`;
}

/**
 * Format a WoW (week-over-week) delta as a labeled indicator.
 * @param delta - Decimal delta string (e.g., "0.12" for +12%), null, or undefined
 * @returns Object with label (e.g., "▲ +12.0%") and positive flag
 */
export function formatWowDelta(
  delta: string | null | undefined,
): { label: string; positive: boolean | null } {
  if (!delta) return { label: "", positive: null };
  const num = parseFloat(delta);
  if (isNaN(num)) return { label: "", positive: null };
  const pct = (num * 100).toFixed(1);
  if (num > 0) return { label: `▲ +${pct}%`, positive: true };
  if (num < 0) return { label: `▼ ${pct}%`, positive: false };
  return { label: "0%", positive: null };
}

/**
 * Get the default date range: last 30 days (today minus 29 days → today).
 * @returns Object with from and to as YYYY-MM-DD strings
 */
export function getDefaultDateRange(): { from: string; to: string } {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - 29); // last 30 days inclusive (D-09)
  const fmt = (d: Date) => d.toISOString().split("T")[0]; // YYYY-MM-DD
  return { from: fmt(from), to: fmt(to) };
}
