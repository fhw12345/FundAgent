/**
 * Date Range Controls - Symbol input and date range selection
 */

interface DateRangeControlsProps {
  currentSymbol: string;
  startDate: string;
  endDate: string;
  onSymbolChange: (symbol: string) => void;
  onStartDateChange: (date: string) => void;
  onEndDateChange: (date: string) => void;
}

export function DateRangeControls({
  currentSymbol,
  startDate,
  endDate,
  onSymbolChange,
  onStartDateChange,
  onEndDateChange,
}: DateRangeControlsProps) {
  const setDateRange = (months: number) => {
    const end = new Date();
    const start = new Date();
    start.setMonth(start.getMonth() - months);
    onStartDateChange(start.toISOString().split("T")[0]);
    onEndDateChange(end.toISOString().split("T")[0]);
  };

  const setYearRange = (years: number) => {
    const end = new Date();
    const start = new Date();
    start.setFullYear(start.getFullYear() - years);
    onStartDateChange(start.toISOString().split("T")[0]);
    onEndDateChange(end.toISOString().split("T")[0]);
  };

  return (
    <div className="mb-4 space-y-3">
      <div className="flex space-x-3">
        <div className="flex-1">
          <label
            htmlFor="symbol-input"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            Stock Symbol
          </label>
          <input
            id="symbol-input"
            type="text"
            value={currentSymbol}
            onChange={(e) => onSymbolChange(e.target.value.toUpperCase())}
            placeholder="e.g., AAPL, TSLA, MSFT"
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            maxLength={10}
          />
        </div>
        <div className="w-36">
          <label
            htmlFor="start-date-input"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            From Date
          </label>
          <input
            id="start-date-input"
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        <div className="w-36">
          <label
            htmlFor="end-date-input"
            className="block text-xs font-medium text-gray-700 mb-1"
          >
            To Date
          </label>
          <input
            id="end-date-input"
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      </div>

      {/* Quick Date Range Buttons */}
      <div className="flex space-x-2">
        <span className="text-xs text-gray-500">Quick ranges:</span>
        <button
          onClick={() => setDateRange(1)}
          className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
        >
          1M
        </button>
        <button
          onClick={() => setDateRange(3)}
          className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
        >
          3M
        </button>
        <button
          onClick={() => setDateRange(6)}
          className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
        >
          6M
        </button>
        <button
          onClick={() => setYearRange(1)}
          className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
        >
          1Y
        </button>
        <button
          onClick={() => setYearRange(2)}
          className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
        >
          2Y
        </button>
      </div>
    </div>
  );
}
