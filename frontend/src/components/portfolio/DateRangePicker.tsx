/**
 * Date Range Picker Component for Portfolio Chat History.
 *
 * Allows filtering portfolio analysis history by date range.
 */

import { useTranslation } from "react-i18next";

interface DateRangePickerProps {
  /** Start date (YYYY-MM-DD format, empty for no filter) */
  startDate: string;
  /** End date (YYYY-MM-DD format, empty for no filter) */
  endDate: string;
  /** Callback when start date changes */
  onStartDateChange: (date: string) => void;
  /** Callback when end date changes */
  onEndDateChange: (date: string) => void;
  /** Callback to clear all date filters */
  onClear: () => void;
}

/**
 * Date range picker for filtering portfolio analysis history.
 *
 * Allows users to select a start date and/or end date to filter
 * historical analyses chronologically.
 */
export function DateRangePicker({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onClear,
}: DateRangePickerProps) {
  const { t } = useTranslation(['portfolio', 'common']);

  const hasFilters = startDate || endDate;

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between mb-2">
        <label className="block text-sm font-medium text-gray-700">
          {t('portfolio:filters.dateRange')}
        </label>
        {hasFilters && (
          <button
            onClick={onClear}
            className="text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {t('common:clear')}
          </button>
        )}
      </div>

      <div className="space-y-2">
        {/* Start Date */}
        <div>
          <label
            htmlFor="start-date"
            className="block text-xs text-gray-600 mb-1"
          >
            {t('portfolio:filters.from')}
          </label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            max={endDate || undefined}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-sm"
          />
        </div>

        {/* End Date */}
        <div>
          <label
            htmlFor="end-date"
            className="block text-xs text-gray-600 mb-1"
          >
            {t('portfolio:filters.to')}
          </label>
          <input
            id="end-date"
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            min={startDate || undefined}
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-sm"
          />
        </div>
      </div>
    </div>
  );
}
