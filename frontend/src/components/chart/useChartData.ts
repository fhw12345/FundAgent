/**
 * useChartData Hook
 *
 * This hook is responsible for converting raw price data into a format
 * that can be consumed by the Lightweight Charts library. It handles timezone
 * conversions and adapts the data structure for line or candlestick charts.
 */

import { useCallback } from "react";
import { Time } from "lightweight-charts";
import { PriceDataPoint } from "../../services/market";

type SupportedTimezone =
  | "US/Eastern"
  | "UTC"
  | "Asia/Shanghai"
  | "Europe/London"
  | "Asia/Tokyo";
type ChartType = "line" | "candlestick";

const convertTimezone = (
  easternTimeStr: string,
  targetTimezone: SupportedTimezone,
): Date => {
  const easternDate = new Date(easternTimeStr + "-05:00"); // EST, TODO: handle EDT (-04:00) detection

  if (targetTimezone === "US/Eastern") {
    return easternDate;
  }

  const timezoneOffsets = {
    UTC: 0,
    "US/Eastern": -5, // EST
    "Asia/Shanghai": 8,
    "Europe/London": 0, // GMT
    "Asia/Tokyo": 9,
  };

  const easternOffset = -5; // EST hours
  const targetOffset = timezoneOffsets[targetTimezone];
  const offsetDiff = targetOffset - easternOffset;

  return new Date(easternDate.getTime() + offsetDiff * 60 * 60 * 1000);
};

export const useChartData = (
  data: PriceDataPoint[],
  chartType: ChartType,
  selectedTimezone: SupportedTimezone,
) => {
  const convertToChartData = useCallback(() => {
    const convertTime = (timeStr: string): Time => {
      if (timeStr.includes("T")) {
        const convertedDate = convertTimezone(timeStr, selectedTimezone);
        return Math.floor(convertedDate.getTime() / 1000) as Time;
      }
      return timeStr as Time;
    };

    const convertedData = data
      .map((point) => ({
        ...point,
        convertedTime: convertTime(point.time),
      }))
      .sort((a, b) => {
        if (
          typeof a.convertedTime === "number" &&
          typeof b.convertedTime === "number"
        ) {
          return a.convertedTime - b.convertedTime;
        }
        return a.convertedTime
          .toString()
          .localeCompare(b.convertedTime.toString());
      });

    if (chartType === "line") {
      return convertedData.map((point) => ({
        time: point.convertedTime,
        value: point.close,
      }));
    } else {
      return convertedData.map((point) => ({
        time: point.convertedTime,
        open: point.open,
        high: point.high,
        low: point.low,
        close: point.close,
      }));
    }
  }, [data, chartType, selectedTimezone]);

  return { convertToChartData };
};
