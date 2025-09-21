/**
 * Interactive Trading Chart Component
 *
 * This component orchestrates the various parts of the trading chart,
 * including the header, the chart itself, and the tooltip. It manages
 * state and passes data and callbacks to its children.
 */

import React, { useState, useRef } from 'react'
import { PriceDataPoint, TimeInterval } from '../../services/market'
import { ChartHeader } from './chart/ChartHeader'
import { ChartTooltip } from './chart/ChartTooltip'
import { useChart } from './chart/useChart'
import { useChartData } from './chart/useChartData'

type SupportedTimezone = 'US/Eastern' | 'UTC' | 'Asia/Shanghai' | 'Europe/London' | 'Asia/Tokyo'

interface TradingChartProps {
  symbol: string
  data: PriceDataPoint[]
  chartType?: 'line' | 'candlestick'
  interval: TimeInterval
  onIntervalChange?: (interval: TimeInterval) => void
  onDateRangeSelect?: (startDate: string, endDate: string) => void
  highlightDateRange?: { start: string; end: string }
  className?: string
}

export const TradingChart: React.FC<TradingChartProps> = ({
  symbol,
  data,
  chartType = 'line',
  interval,
  onIntervalChange,
  onDateRangeSelect,
  highlightDateRange,
  className = ''
}) => {
  const chartContainerRef = useRef<HTMLDivElement>(null)
  const [selectedTimezone, setSelectedTimezone] = useState<SupportedTimezone>('US/Eastern')
  const [dateSelection, setDateSelection] = useState<{ startDate: string | null; endDate: string | null; clickCount: number }>({
    startDate: null,
    endDate: null,
    clickCount: 0
  });

  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, time: '', price: 0 });

  const handleDateRangeSelect = (startDate: string, endDate: string) => {
    setDateSelection({ startDate, endDate, clickCount: 0 });
    onDateRangeSelect?.(startDate, endDate);
  };

  const { chartRef, seriesRef, setChartData } = useChart(chartContainerRef, chartType, handleDateRangeSelect, setTooltip, interval);
  const { convertToChartData } = useChartData(data, chartType, selectedTimezone);

  React.useEffect(() => {
    const chartData = convertToChartData();
    setChartData(chartData, highlightDateRange);
  }, [data, convertToChartData, setChartData, highlightDateRange]);

  return (
    <div className={`relative ${className}`}>
      <ChartHeader
        symbol={symbol}
        interval={interval}
        selectedTimezone={selectedTimezone}
        dateSelection={dateSelection}
        onIntervalChange={onIntervalChange}
        onTimezoneChange={setSelectedTimezone}
      />
      <div className="relative">
        <div ref={chartContainerRef} className="w-full h-96 border rounded-lg" />
        <ChartTooltip tooltipData={tooltip} chartContainerRef={chartContainerRef} />
      </div>
    </div>
  )
}