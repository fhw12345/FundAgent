/**
 * Portfolio value chart with clickable analysis markers.
 *
 * Clean Robinhood-style chart showing portfolio performance over time.
 * Uses lightweight-charts for smooth, professional rendering.
 */

import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, IChartApi, ISeriesApi, LineData } from "lightweight-charts";

interface ChartDataPoint {
  time: number; // Unix timestamp in seconds
  value: number;
}

interface AnalysisMarker {
  time: number;
  position: "aboveBar" | "belowBar";
  color: string;
  shape: "circle";
  text: string;
}

interface PortfolioChartProps {
  data: ChartDataPoint[];
  markers?: AnalysisMarker[];
  onMarkerClick?: (marker: AnalysisMarker) => void;
}

export function PortfolioChart({ data, markers = [], onMarkerClick }: PortfolioChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "white" },
        textColor: "#71717A", // gray-500
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: "#E5E7EB" }, // gray-200
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
      timeScale: {
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderVisible: false,
      },
      crosshair: {
        horzLine: {
          visible: false,
          labelVisible: false,
        },
        vertLine: {
          labelVisible: false,
        },
      },
    });

    // Create line series
    const lineSeries = chart.addLineSeries({
      color: "#F59E0B", // amber-500 (Robinhood yellow)
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    chartRef.current = chart;
    seriesRef.current = lineSeries;
    setIsReady(true);

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, []);

  // Update data when it changes
  useEffect(() => {
    if (!isReady || !seriesRef.current || data.length === 0) return;

    const chartData: LineData[] = data.map((point) => ({
      time: point.time as any,
      value: point.value,
    }));

    seriesRef.current.setData(chartData);

    // Add markers if any (must be sorted by time ascending)
    if (markers.length > 0 && seriesRef.current) {
      const sortedMarkers = [...markers].sort((a, b) => a.time - b.time);
      seriesRef.current.setMarkers(sortedMarkers as any);
    }

    // Fit content
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [isReady, data, markers]);

  // Add click handler for markers
  useEffect(() => {
    if (!chartRef.current || !onMarkerClick) return;

    const chart = chartRef.current;

    const handleClick = (param: any) => {
      if (!param.time || !param.point) return;

      // Find marker at clicked time (within tolerance)
      const clickedTime = param.time;
      const tolerance = 60 * 60; // 1 hour tolerance in seconds

      const clickedMarker = markers.find((marker) => {
        return Math.abs(marker.time - clickedTime) < tolerance;
      });

      if (clickedMarker && onMarkerClick) {
        onMarkerClick(clickedMarker);
      }
    };

    chart.subscribeClick(handleClick);

    return () => {
      chart.unsubscribeClick(handleClick);
    };
  }, [chartRef.current, markers, onMarkerClick]);

  return <div ref={chartContainerRef} className="w-full" />;
}
