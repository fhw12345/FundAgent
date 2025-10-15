/**
 * Interactive Trading Chart Component
 *
 * This component orchestrates the various parts of the trading chart,
 * including the header, the chart itself, and the tooltip. It manages
 * state and passes data and callbacks to its children.
 */

import React, { useState, useRef } from "react";
import { PriceDataPoint, TimeInterval } from "../services/market";
import { ChartHeader } from "./chart/ChartHeader";
import { ChartTooltip } from "./chart/ChartTooltip";
import { useChart } from "./chart/useChart";
import { useChartData } from "./chart/useChartData";

type SupportedTimezone =
  | "US/Eastern"
  | "UTC"
  | "Asia/Shanghai"
  | "Europe/London"
  | "Asia/Tokyo";

interface FibonacciLevel {
  level: number;
  price: number;
  percentage: string;
  is_key_level: boolean;
}

interface PressureZone {
  center_price: number;
  upper_bound: number;
  lower_bound: number;
  zone_width: number;
}

interface TopTrend {
  rank: number;
  type: string;
  period: string;
  magnitude: number;
  high: number;
  low: number;
}

interface FibonacciAnalysisData {
  fibonacci_levels: FibonacciLevel[];
  pressure_zone: PressureZone | null;
  raw_data?: {
    top_trends?: TopTrend[];
    pressure_zones?: Array<PressureZone & { trend_type: string }>;
  };
}

interface TradingChartProps {
  symbol: string;
  data: PriceDataPoint[];
  chartType?: "line" | "candlestick";
  interval: TimeInterval;
  onIntervalChange?: (interval: TimeInterval) => void;
  onDateRangeSelect?: (startDate: string, endDate: string) => void;
  highlightDateRange?: { start: string; end: string };
  fibonacciAnalysis?: FibonacciAnalysisData | null;
  className?: string;
}

export const TradingChart: React.FC<TradingChartProps> = ({
  symbol,
  data,
  chartType = "candlestick",
  interval,
  onIntervalChange,
  onDateRangeSelect,
  highlightDateRange,
  fibonacciAnalysis,
  className = "",
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const [selectedTimezone, setSelectedTimezone] =
    useState<SupportedTimezone>("US/Eastern");
  const [dateSelection, setDateSelection] = useState<{
    startDate: string | null;
    endDate: string | null;
    clickCount: number;
  }>({
    startDate: null,
    endDate: null,
    clickCount: 0,
  });

  const [tooltip, setTooltip] = useState({
    visible: false,
    x: 0,
    y: 0,
    time: "",
    price: 0,
  });
  const [lastSyncTime, setLastSyncTime] = useState<Date | null>(null);

  const handleDateRangeSelect = (startDate: string, endDate: string) => {
    setDateSelection({ startDate, endDate, clickCount: 0 });
    onDateRangeSelect?.(startDate, endDate);
  };

  const { setChartData } = useChart(
    chartContainerRef,
    chartType,
    handleDateRangeSelect,
    setTooltip,
    interval,
    fibonacciAnalysis,
    data,
  );
  const { convertToChartData } = useChartData(
    data,
    chartType,
    selectedTimezone,
  );

  React.useEffect(() => {
    const chartData = convertToChartData();
    setChartData(chartData, highlightDateRange);
    // Update last sync time when data changes
    if (data && data.length > 0) {
      setLastSyncTime(new Date());
    }
  }, [data, convertToChartData, setChartData, highlightDateRange]);

  // Calculate date range from actual chart data
  const actualDateRange = React.useMemo(() => {
    if (!data || data.length === 0) return null;

    const startDate = new Date(data[0].time);
    const endDate = new Date(data[data.length - 1].time);

    // Format as YYYY-MM-DD
    const formatDate = (date: Date) => {
      return date.toISOString().split('T')[0];
    };

    return {
      start: formatDate(startDate),
      end: formatDate(endDate),
    };
  }, [data]);

  // Use highlightDateRange if available (from Fibonacci/Stochastic), otherwise use actual data range
  const displayDateRange = highlightDateRange || actualDateRange || undefined;

  return (
    <div className={`relative ${className}`}>
      <ChartHeader
        symbol={symbol}
        interval={interval}
        selectedTimezone={selectedTimezone}
        dateSelection={dateSelection}
        onIntervalChange={onIntervalChange}
        onTimezoneChange={setSelectedTimezone}
        highlightDateRange={displayDateRange}
        lastSyncTime={lastSyncTime}
      />
      <div className="relative">
        <div
          ref={chartContainerRef}
          className="w-full h-96 border rounded-lg"
        />
        <ChartTooltip
          tooltipData={tooltip}
          chartContainerRef={chartContainerRef}
        />
      </div>
    </div>
  );
};
