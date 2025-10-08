/**
 * ChartHeader Component
 *
 * Handles the display of the chart symbol, date selection status,
 * and provides controls for timezone and time interval.
 */

import React from "react";
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
}

export const ChartHeader: React.FC<ChartHeaderProps> = ({
  symbol,
  interval,
  selectedTimezone,
  dateSelection,
  onIntervalChange,
  onTimezoneChange,
}) => {
  return (
    <div className="flex items-center justify-between mb-4">
      <div className="flex-1">
        <h3 className="text-lg font-semibold">{symbol}</h3>
        {dateSelection.startDate && (
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
