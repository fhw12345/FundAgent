/**
 * Date Range Calculator Utility
 *
 * Centralizes date range calculation logic to avoid duplication across components.
 */

export type TimeInterval = "1h" | "1d" | "1w" | "1mo";

export interface DateRange {
  start: string;
  end: string;
}

/**
 * Calculate date range for a given interval.
 * If selectedDateRange has values, returns them unchanged.
 * Otherwise, calculates appropriate start/end dates based on interval.
 *
 * @param selectedDateRange - User-selected date range (may be empty)
 * @param interval - Time interval (1h, 1d, 1w, 1mo)
 * @returns Date range with start/end in YYYY-MM-DD format
 */
export function calculateDateRange(
  selectedDateRange: DateRange,
  interval: TimeInterval,
): DateRange {
  // If user has selected custom dates, use them
  if (selectedDateRange.start && selectedDateRange.end) {
    return selectedDateRange;
  }

  // Otherwise, calculate default range based on interval
  const today = new Date();
  let periodsBack: Date;

  switch (interval) {
    case "1h":
      // 1-hour interval: last 30 days
      periodsBack = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
      break;
    case "1w":
      // 1-week interval: last 1 year
      periodsBack = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000);
      break;
    case "1mo":
      // 1-month interval: last 2 years
      periodsBack = new Date(today.getTime() - 2 * 365 * 24 * 60 * 60 * 1000);
      break;
    default:
      // 1-day interval (default): last 6 months
      periodsBack = new Date(today.getTime() - 6 * 30 * 24 * 60 * 60 * 1000);
  }

  return {
    start: periodsBack.toISOString().split("T")[0],
    end: today.toISOString().split("T")[0],
  };
}

/**
 * Get the default period string for React Query price data endpoint.
 * This is used when no custom date range is selected.
 *
 * @param interval - Time interval
 * @returns Period string for API (e.g., "1mo", "6mo", "1y", "2y")
 */
export function getPeriodForInterval(interval: TimeInterval): string {
  switch (interval) {
    case "1h":
      return "1mo";
    case "1d":
      return "6mo";
    case "1w":
      return "1y";
    case "1mo":
      return "2y";
    default:
      return "6mo";
  }
}
