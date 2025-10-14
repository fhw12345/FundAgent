/**
 * Chart Panel Component
 *
 * This component displays the trading chart and related controls,
 * such as symbol search and quick analysis buttons.
 */
import React, { memo } from "react";
import { SymbolSearch } from "../SymbolSearch";
import { TradingChart } from "../TradingChart";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Loader2,
  LineChart,
  Zap,
  Activity,
} from "lucide-react";
import { TimeInterval } from "../../services/market";
import type { FibonacciMetadata } from "../../utils/analysisMetadataExtractor";

interface ChartPanelProps {
  currentSymbol: string;
  currentCompanyName: string;
  priceDataQuery: any;
  selectedInterval: TimeInterval;
  selectedDateRange: { start: string; end: string };
  analysisMutation: any;
  fibonacciAnalysis: FibonacciMetadata | null;
  handleSymbolSelect: (symbol: string, name: string) => void;
  handleIntervalChange: (interval: TimeInterval) => void;
  handleDateRangeSelect: (startDate: string, endDate: string) => void;
  handleQuickAnalysis: (
    type: "fibonacci" | "fundamentals" | "macro" | "stochastic",
  ) => void;
}

const ChartPanelComponent: React.FC<ChartPanelProps> = ({
  currentSymbol,
  currentCompanyName,
  priceDataQuery,
  selectedInterval,
  selectedDateRange,
  analysisMutation,
  fibonacciAnalysis,
  handleSymbolSelect,
  handleIntervalChange,
  handleDateRangeSelect,
  handleQuickAnalysis,
}) => {
  return (
    <div className="flex flex-col w-1/2 h-full">
      <div className="border-b p-4 bg-gray-50">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-medium text-gray-900">
              Trading Charts
            </h3>
            <p className="text-sm text-gray-500">
              Search symbols and view interactive charts
            </p>
          </div>
          {currentSymbol && (
            <div className="text-right">
              <div className="text-lg font-semibold text-gray-900">
                {currentSymbol}
              </div>
              <div className="text-sm text-gray-600">{currentCompanyName}</div>
              {priceDataQuery.data?.data.length > 0 && (
                <div className="text-sm font-medium text-green-600">
                  $
                  {priceDataQuery.data.data[
                    priceDataQuery.data.data.length - 1
                  ].close.toFixed(2)}
                </div>
              )}
            </div>
          )}
        </div>

        <SymbolSearch onSymbolSelect={handleSymbolSelect} className="mb-4" />

        {currentSymbol && (
          <div className="flex gap-2 flex-wrap">
            <div className="relative group">
              <button
                onClick={() => handleQuickAnalysis("fibonacci")}
                disabled={analysisMutation.isPending}
                className="flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm transition-all"
              >
                <BarChart3 className="h-4 w-4" />
                Fibonacci
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900/50 backdrop-blur-sm text-white text-sm font-medium rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-50 shadow-lg border border-white/20">
                Identify key support/resistance levels using Fibonacci
                retracement
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900/50"></div>
              </div>
            </div>
            <div className="relative group">
              <button
                onClick={() => handleQuickAnalysis("fundamentals")}
                disabled={analysisMutation.isPending}
                className="flex items-center gap-2 px-3 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 text-sm transition-all"
              >
                <DollarSign className="h-4 w-4" />
                Fundamentals
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900/50 backdrop-blur-sm text-white text-sm font-medium rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-50 shadow-lg border border-white/20">
                View company metrics: P/E ratio, market cap, dividend yield,
                volume
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900/50"></div>
              </div>
            </div>
            <div className="relative group">
              <button
                onClick={() => handleQuickAnalysis("macro")}
                disabled={analysisMutation.isPending}
                className="flex items-center gap-2 px-3 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 text-sm transition-all"
              >
                <TrendingUp className="h-4 w-4" />
                Macro
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900/50 backdrop-blur-sm text-white text-sm font-medium rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-50 shadow-lg border border-white/20">
                Analyze overall market sentiment, VIX level, and sector
                performance
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900/50"></div>
              </div>
            </div>
            <div className="relative group">
              <button
                onClick={() => handleQuickAnalysis("stochastic")}
                disabled={analysisMutation.isPending}
                className="flex items-center gap-2 px-3 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 text-sm transition-all"
              >
                <Activity className="h-4 w-4" />
                Stochastic
              </button>
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900/50 backdrop-blur-sm text-white text-sm font-medium rounded-lg whitespace-nowrap opacity-0 group-hover:opacity-100 transition-all duration-200 pointer-events-none z-50 shadow-lg border border-white/20">
                Measure momentum to identify overbought/oversold conditions
                (%K/%D)
                <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-1 border-4 border-transparent border-t-gray-900/50"></div>
              </div>
            </div>
            {selectedDateRange.start && selectedDateRange.end && (
              <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm">
                <Zap className="h-4 w-4" />
                {selectedDateRange.start} to {selectedDateRange.end}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex-1 p-4 overflow-y-auto">
        {!currentSymbol && (
          <div className="h-full border rounded-lg flex items-center justify-center text-sm text-gray-500 bg-gray-50">
            <div className="text-center">
              <LineChart className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <p>Search for a stock symbol above to view its chart</p>
              <p className="text-xs mt-2">
                Try searching &quot;apple&quot;, &quot;tesla&quot;, or any
                company name
              </p>
            </div>
          </div>
        )}
        {currentSymbol && priceDataQuery.isLoading && (
          <div className="h-full border rounded-lg flex items-center justify-center text-sm text-gray-500">
            <div className="text-center">
              <Loader2 className="h-8 w-8 animate-spin mx-auto mb-2" />
              Loading price data...
            </div>
          </div>
        )}
        {currentSymbol &&
          priceDataQuery.isError &&
          priceDataQuery.error?.suggestions && (
            <div className="p-4 border rounded-lg bg-red-50 text-sm text-red-700">
              {priceDataQuery.error.message || "Price data unavailable."}
              <div className="mt-2 flex flex-wrap gap-2">
                {priceDataQuery.error.suggestions.map((s: any) => (
                  <button
                    key={s.symbol}
                    onClick={() => handleSymbolSelect(s.symbol, s.name)}
                    className="px-2 py-1 text-xs bg-white border rounded hover:bg-blue-50"
                  >
                    {s.symbol} {s.name && `- ${s.name}`}
                  </button>
                ))}
              </div>
            </div>
          )}
        {currentSymbol && priceDataQuery.data && !priceDataQuery.isError && (
          <div className="h-full">
            <TradingChart
              symbol={currentSymbol}
              data={priceDataQuery.data.data}
              interval={selectedInterval}
              onIntervalChange={handleIntervalChange}
              onDateRangeSelect={handleDateRangeSelect}
              highlightDateRange={
                selectedDateRange.start && selectedDateRange.end
                  ? selectedDateRange
                  : undefined
              }
              fibonacciAnalysis={fibonacciAnalysis as any}
              className="bg-white rounded-lg border h-full"
            />
            {priceDataQuery.isRefetching && (
              <div className="text-xs text-gray-500 mt-1 flex items-center">
                <Loader2 className="h-3 w-3 animate-spin mr-1" />
                Updating price data...
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

// Custom comparison function to prevent unnecessary re-renders
// Only re-render if actual data changes, not query loading states
const arePropsEqual = (prev: ChartPanelProps, next: ChartPanelProps) => {
  return (
    prev.currentSymbol === next.currentSymbol &&
    prev.currentCompanyName === next.currentCompanyName &&
    prev.selectedInterval === next.selectedInterval &&
    prev.selectedDateRange.start === next.selectedDateRange.start &&
    prev.selectedDateRange.end === next.selectedDateRange.end &&
    prev.fibonacciAnalysis === next.fibonacciAnalysis &&
    // Only compare query data, not loading states
    prev.priceDataQuery.data === next.priceDataQuery.data &&
    prev.priceDataQuery.isLoading === next.priceDataQuery.isLoading &&
    prev.priceDataQuery.isError === next.priceDataQuery.isError &&
    // Callbacks should be stable (useCallback in parent)
    prev.handleSymbolSelect === next.handleSymbolSelect &&
    prev.handleIntervalChange === next.handleIntervalChange &&
    prev.handleDateRangeSelect === next.handleDateRangeSelect &&
    prev.handleQuickAnalysis === next.handleQuickAnalysis &&
    // Mutation pending state
    prev.analysisMutation.isPending === next.analysisMutation.isPending
  );
};

// Memoize to prevent unnecessary re-renders
export const ChartPanel = memo(ChartPanelComponent, arePropsEqual);
