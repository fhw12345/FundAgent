/**
 * ChartHeader Component
 *
 * Handles the display of the chart symbol, date selection status,
 * and provides controls for timezone and time interval.
 */

import React from "react";
import { CheckCircle2 } from "lucide-react";
import { TimeInterval } from "../../services/market";

type SupportedTimezone =
  | "US/Eastern"
  | "UTC"
  | "Asia/Shanghai"
  | "Europe/London"
  | "Asia/Tokyo";

const TIMEZONE_OPTIONS: { value: SupportedTimezone; label: string }[] = [
  { value: "US/Eastern", label: "US Eastern (Market Time)" },
  { value: "UTC", label: "UTC" },
  { value: "Asia/Shanghai", label: "Asia/Shanghai (UTC+8)" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Asia/Tokyo", label: "Asia/Tokyo" },
];

const INTERVAL_BUTTONS: { key: TimeInterval; label: string; period: string }[] =
  [
    { key: "1h", label: "1H", period: "1mo" },
    { key: "1d", label: "1D", period: "6mo" },
    { key: "1w", label: "1W", period: "1y" },
    { key: "1mo", label: "1M", period: "2y" },
  ];

interface ChartHeaderProps {
  symbol: string;
  interval: TimeInterval;
  selectedTimezone: SupportedTimezone;
  dateSelection: {
    startDate: string | null;
    endDate: string | null;
    clickCount: number;
  };
  onIntervalChange?: (interval: TimeInterval) => void;
  onTimezoneChange: (timezone: SupportedTimezone) => void;
  highlightDateRange?: { start: string; end: string };
  lastSyncTime?: Date | null;
}

export const ChartHeader: React.FC<ChartHeaderProps> = ({
  symbol,
  interval,
  selectedTimezone,
  dateSelection,
  onIntervalChange,
  onTimezoneChange,
  highlightDateRange,
  lastSyncTime,
}) => {
  // Calculate days between start and end dates
  const daysDiff = React.useMemo(() => {
    if (!highlightDateRange?.start || !highlightDateRange?.end) return null;
    const start = new Date(highlightDateRange.start);
    const end = new Date(highlightDateRange.end);
    return Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
  }, [highlightDateRange]);

  // Force re-render every 30 seconds to update "X seconds/minutes ago"
  const [tick, setTick] = React.useState(0);
  React.useEffect(() => {
    const interval = setInterval(() => {
      setTick((prev) => prev + 1);
    }, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Format last sync time for tooltip (recalculates every 30s due to tick)
  const syncTimeTooltip = React.useMemo(() => {
    if (!lastSyncTime) return "Data loaded";
    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - lastSyncTime.getTime()) / 1000);

    if (diffSeconds < 60) {
      return `Last synced: ${diffSeconds} seconds ago`;
    } else if (diffSeconds < 3600) {
      const minutes = Math.floor(diffSeconds / 60);
      return `Last synced: ${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    } else {
      const hours = Math.floor(diffSeconds / 3600);
      return `Last synced: ${hours} hour${hours > 1 ? 's' : ''} ago`;
    }
  }, [lastSyncTime, tick]);

  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">{symbol}</h3>
          {highlightDateRange && (
            <div className="relative group">
              <span className="inline-flex items-center gap-1 px-2 py-1 bg-green-50 text-green-700 text-xs rounded-md border border-green-200 cursor-help">
                <CheckCircle2 className="h-3 w-3" />
                {highlightDateRange.start} to {highlightDateRange.end} ({daysDiff}{" "}
                {daysDiff === 1 ? "day" : "days"})
              </span>
              {/* Modern tooltip below */}
              <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 px-3 py-2 bg-white border border-gray-200 text-gray-700 text-xs rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50 shadow-lg">
                {syncTimeTooltip}
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 -mb-1 border-4 border-transparent border-b-white"></div>
                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-0 border-4 border-transparent border-b-gray-200"></div>
              </div>
            </div>
          )}
        </div>
        {dateSelection.startDate && !highlightDateRange && (
          <div className="mt-1">
            {dateSelection.clickCount === 1 ? (
              <span className="inline-flex items-center px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                📅 Start: {dateSelection.startDate} • Click again for end date
              </span>
            ) : dateSelection.endDate ? (
              <span className="inline-flex items-center px-2 py-1 bg-green-100 text-green-800 text-xs rounded-full">
                📊 Range: {dateSelection.startDate} to {dateSelection.endDate}
              </span>
            ) : null}
          </div>
        )}
      </div>

      <div className="flex gap-2 items-center">
        <select
          value={selectedTimezone}
          onChange={(e) =>
            onTimezoneChange(e.target.value as SupportedTimezone)
          }
          className="text-xs border border-gray-300 rounded px-2 py-1 bg-white min-w-[140px]"
        >
          {TIMEZONE_OPTIONS.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>

        <div className="flex gap-1 bg-gray-100 rounded-md p-1">
          {INTERVAL_BUTTONS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => onIntervalChange?.(key)}
              className={`px-3 py-1 text-sm rounded transition-colors ${
                interval === key
                  ? "bg-blue-500 text-white"
                  : "text-gray-600 hover:bg-gray-200"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
