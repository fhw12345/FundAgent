/**
 * Chart Panel Component
 *
 * This component displays the trading chart and related controls,
 * such as symbol search and quick analysis buttons.
 */
import React, { memo } from "react";
import { UseQueryResult, UseMutationResult } from "@tanstack/react-query";
import { SymbolSearch } from "../SymbolSearch";
import { TradingChart } from "../TradingChart";
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Loader2,
  LineChart,
  Activity,
  ChevronRight,
  ChevronLeft,
  Newspaper,
  Building2,
  FileText,
  ArrowUpDown,
} from "lucide-react";
import { TimeInterval, PriceDataResponse } from "../../services/market";
import type { FibonacciMetadata } from "../../utils/analysisMetadataExtractor";

interface ChartPanelProps {
  currentSymbol: string;
  currentCompanyName: string;
  priceDataQuery: UseQueryResult<PriceDataResponse, Error>;
  selectedInterval: TimeInterval;
  selectedDateRange: { start: string; end: string };
  analysisMutation: UseMutationResult<unknown, Error, string>;
  fibonacciAnalysis: FibonacciMetadata | null;
  handleSymbolSelect: (symbol: string, name: string) => void;
  handleIntervalChange: (interval: TimeInterval) => void;
  handleDateRangeSelect: (startDate: string, endDate: string) => void;
  handleQuickAnalysis: (
    type: "fibonacci" | "company_overview" | "macro" | "stochastic" | "news_sentiment" | "cash_flow" | "balance_sheet" | "market_movers",
  ) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
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
  isCollapsed,
  onToggleCollapse,
}) => {

  return (
    <div className={`flex flex-col h-full transition-all duration-200 relative ${isCollapsed ? 'w-12' : 'w-full'}`}>
      {/* Artistic Collapse/Expand Toggle - Vertical Bar Design */}
      {isCollapsed && (
        <div className="w-12 h-full flex flex-col bg-gradient-to-b from-white/80 to-gray-50/80 backdrop-blur-xl border-l border-gray-200/50 items-center justify-center relative">
          <button
            onClick={onToggleCollapse}
            className="group relative"
            title="Expand chart panel"
          >
            {/* Vertical bar with hover effect */}
            <div className="w-1 h-16 bg-gradient-to-b from-blue-400 via-indigo-500 to-blue-600 rounded-full transition-all duration-300 group-hover:h-20 group-hover:w-1.5 group-hover:shadow-lg group-hover:shadow-blue-500/50" />
            {/* Chevron icon overlay */}
            <div className="absolute inset-0 flex items-center justify-center">
              <ChevronLeft size={16} strokeWidth={2.5} className="text-indigo-600 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
            </div>
          </button>
        </div>
      )}

      <button
        onClick={onToggleCollapse}
        className={`group absolute left-0 top-1/2 -translate-y-1/2 z-10 ${isCollapsed ? 'hidden' : ''}`}
        title="Collapse chart panel"
      >
        {/* Elegant vertical bar that peeks from edge */}
        <div className="relative flex items-center">
          <div className="w-1 h-16 bg-gradient-to-b from-blue-400 via-indigo-500 to-blue-600 rounded-r-full transition-all duration-300 group-hover:h-20 group-hover:w-1.5 group-hover:shadow-lg group-hover:shadow-blue-500/50" />
          {/* Chevron appears on hover */}
          <div className="absolute left-2 opacity-0 group-hover:opacity-100 transition-all duration-200 group-hover:translate-x-1">
            <div className="bg-white/90 backdrop-blur-sm rounded-full p-1.5 shadow-md">
              <ChevronRight size={14} strokeWidth={2.5} className="text-indigo-600" />
            </div>
          </div>
        </div>
      </button>

      <div className={isCollapsed ? 'hidden' : 'flex flex-col h-full'}>
      <div className="border-b p-3 bg-gray-50">
        {/* Title and Symbol in one line */}
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-lg font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent">
              Trading Charts
            </h3>
          </div>
          {currentSymbol && priceDataQuery.data?.data && priceDataQuery.data.data.length > 0 && (
            <div className="flex items-center gap-2">
              <div className="text-right">
                <div className="text-base font-semibold text-gray-900">{currentSymbol}</div>
                <div className="text-xs text-gray-500">{currentCompanyName}</div>
              </div>
              <div className="text-lg font-bold text-green-600">
                ${priceDataQuery.data?.data[priceDataQuery.data.data.length - 1].close.toFixed(2)}
              </div>
            </div>
          )}
        </div>

        {/* Symbol Search */}
        <SymbolSearch onSymbolSelect={handleSymbolSelect} className="mb-3" />

        {/* Analysis Buttons - Only show when symbol selected */}
        {currentSymbol && (
          <div className="space-y-2">
            {/* Technical Analysis - Hidden for 1min interval (insufficient data) */}
            {selectedInterval !== "1m" && (
              <div>
                <div className="text-xs font-medium text-gray-500 mb-1.5">Technical Analysis</div>
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={() => handleQuickAnalysis("fibonacci")}
                    disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                  >
                    {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <BarChart3 className="h-3.5 w-3.5" />}
                    Fibonacci
                  </button>
                  <button
                    onClick={() => handleQuickAnalysis("stochastic")}
                    disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                  >
                    {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
                    Stochastic
                  </button>
                </div>
              </div>
            )}

            {/* Fundamental Analysis */}
            <div>
              <div className="text-xs font-medium text-gray-500 mb-1.5">Fundamental Analysis</div>
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => handleQuickAnalysis("company_overview")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Building2 className="h-3.5 w-3.5" />}
                  Overview
                </button>
                <button
                  onClick={() => handleQuickAnalysis("cash_flow")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-teal-500 text-white rounded-lg hover:bg-teal-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  Cash Flow
                </button>
                <button
                  onClick={() => handleQuickAnalysis("balance_sheet")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-cyan-500 text-white rounded-lg hover:bg-cyan-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileText className="h-3.5 w-3.5" />}
                  Balance Sheet
                </button>
              </div>
            </div>

            {/* Market Sentiment */}
            <div>
              <div className="text-xs font-medium text-gray-500 mb-1.5">Market Sentiment</div>
              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={() => handleQuickAnalysis("news_sentiment")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-amber-500 text-white rounded-lg hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Newspaper className="h-3.5 w-3.5" />}
                  News Sentiment
                </button>
                <button
                  onClick={() => handleQuickAnalysis("macro")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <TrendingUp className="h-3.5 w-3.5" />}
                  Macro
                </button>
                <button
                  onClick={() => handleQuickAnalysis("market_movers")}
                  disabled={analysisMutation.isPending || priceDataQuery.isLoading}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 bg-rose-500 text-white rounded-lg hover:bg-rose-600 disabled:opacity-50 disabled:cursor-not-allowed text-xs transition-all"
                >
                  {priceDataQuery.isLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ArrowUpDown className="h-3.5 w-3.5" />}
                  Market Movers
                </button>
              </div>
            </div>
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
          (priceDataQuery.error as any)?.suggestions && (
            <div className="p-4 border rounded-lg bg-red-50 text-sm text-red-700">
              {priceDataQuery.error.message || "Price data unavailable."}
              <div className="mt-2 flex flex-wrap gap-2">
                {(priceDataQuery.error as any).suggestions.map((s: any) => (
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
