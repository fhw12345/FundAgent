/**
 * Chart Panel Component
 *
 * This component displays the trading chart and related controls,
 * such as symbol search and quick analysis buttons.
 */
import React from 'react'
import { SymbolSearch } from '../SymbolSearch'
import { TradingChart } from '../TradingChart'
import { BarChart3, TrendingUp, DollarSign, Loader2, LineChart, Zap, Activity } from 'lucide-react'
import { TimeInterval, PriceDataPoint } from '../../services/market'
import type { FibonacciAnalysisResponse } from '../../services/analysis'

interface ChartPanelProps {
    currentSymbol: string;
    currentCompanyName: string;
    priceDataQuery: any;
    selectedInterval: TimeInterval;
    selectedDateRange: { start: string; end: string };
    analysisMutation: any;
    fibonacciAnalysis: FibonacciAnalysisResponse | null;
    handleSymbolSelect: (symbol: string, name: string) => void;
    handleIntervalChange: (interval: TimeInterval) => void;
    handleDateRangeSelect: (startDate: string, endDate: string) => void;
    handleQuickAnalysis: (type: 'fibonacci' | 'fundamentals' | 'macro' | 'stochastic') => void;
}

export const ChartPanel: React.FC<ChartPanelProps> = ({
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
        <div className="flex flex-col w-1/2">
            <div className="border-b p-4 bg-gray-50">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-lg font-medium text-gray-900">Trading Charts</h3>
                        <p className="text-sm text-gray-500">Search symbols and view interactive charts</p>
                    </div>
                    {currentSymbol && (
                        <div className="text-right">
                            <div className="text-lg font-semibold text-gray-900">{currentSymbol}</div>
                            <div className="text-sm text-gray-600">{currentCompanyName}</div>
                            {priceDataQuery.data?.data.length > 0 && (
                                <div className="text-sm font-medium text-green-600">
                                    ${priceDataQuery.data.data[priceDataQuery.data.data.length - 1].close.toFixed(2)}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                <SymbolSearch
                    onSymbolSelect={handleSymbolSelect}
                    className="mb-4"
                    autoFocus
                />

                {currentSymbol && (
                    <div className="flex gap-2 flex-wrap">
                        <button
                            onClick={() => handleQuickAnalysis('fibonacci')}
                            disabled={analysisMutation.isPending}
                            className="flex items-center gap-2 px-3 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 text-sm"
                        >
                            <BarChart3 className="h-4 w-4" />
                            Fibonacci
                        </button>
                        <button
                            onClick={() => handleQuickAnalysis('fundamentals')}
                            disabled={analysisMutation.isPending}
                            className="flex items-center gap-2 px-3 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 text-sm"
                        >
                            <DollarSign className="h-4 w-4" />
                            Fundamentals
                        </button>
                        <button
                            onClick={() => handleQuickAnalysis('macro')}
                            disabled={analysisMutation.isPending}
                            className="flex items-center gap-2 px-3 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 text-sm"
                        >
                            <TrendingUp className="h-4 w-4" />
                            Macro
                        </button>
                        <button
                            onClick={() => handleQuickAnalysis('stochastic')}
                            disabled={analysisMutation.isPending}
                            className="flex items-center gap-2 px-3 py-2 bg-indigo-500 text-white rounded-lg hover:bg-indigo-600 disabled:opacity-50 text-sm"
                        >
                            <Activity className="h-4 w-4" />
                            Stochastic
                        </button>
                        {selectedDateRange.start && selectedDateRange.end && (
                            <div className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm">
                                <Zap className="h-4 w-4" />
                                {selectedDateRange.start} to {selectedDateRange.end}
                            </div>
                        )}
                    </div>
                )}
            </div>

            <div className="flex-1 p-4">
                {!currentSymbol && (
                    <div className="h-full border rounded-lg flex items-center justify-center text-sm text-gray-500 bg-gray-50">
                        <div className="text-center">
                            <LineChart className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                            <p>Search for a stock symbol above to view its chart</p>
                            <p className="text-xs mt-2">Try searching "apple", "tesla", or any company name</p>
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
                {currentSymbol && priceDataQuery.isError && (priceDataQuery.error as any)?.suggestions && (
                    <div className="p-4 border rounded-lg bg-red-50 text-sm text-red-700">
                        {(priceDataQuery.error as any).message || 'Price data unavailable.'}
                        <div className="mt-2 flex flex-wrap gap-2">
                            {(priceDataQuery.error as any).suggestions.map((s: any) => (
                                <button key={s.symbol} onClick={() => handleSymbolSelect(s.symbol, s.name)} className="px-2 py-1 text-xs bg-white border rounded hover:bg-blue-50">
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
                            highlightDateRange={selectedDateRange.start && selectedDateRange.end ? selectedDateRange : undefined}
                            fibonacciAnalysis={fibonacciAnalysis}
                            className="bg-white rounded-lg border h-full"
                        />
                        {selectedDateRange.start && selectedDateRange.end && (
                            <div className="text-sm text-gray-600 mt-2 px-4">
                                📊 Chart synchronized with analysis date range: {selectedDateRange.start} to {selectedDateRange.end}
                            </div>
                        )}
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
    )
}