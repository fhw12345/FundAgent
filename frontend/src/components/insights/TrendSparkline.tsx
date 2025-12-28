/**
 * TrendSparkline component for displaying compact trend visualization.
 * Uses SVG path for minimal bundle size and fast rendering.
 */

import type { TrendDataPoint } from "../../types/insights";

interface TrendSparklineProps {
  /** Trend data points (newest first) */
  data: TrendDataPoint[];
  /** Whether to highlight today's datapoint */
  highlightToday?: boolean;
  /** Optional CSS class name */
  className?: string;
  /** Width of the sparkline in pixels */
  width?: number;
  /** Height of the sparkline in pixels */
  height?: number;
}

/**
 * Compact sparkline visualization for trend data.
 * Shows trend direction with color-coded line and optional today marker.
 */
export function TrendSparkline({
  data,
  highlightToday = true,
  className = "",
  width = 120,
  height = 24,
}: TrendSparklineProps) {
  // Handle empty data
  if (data.length === 0) {
    return (
      <div
        className={`flex items-center justify-center text-xs text-gray-400 ${className}`}
        style={{ width, height }}
      >
        No trend data
      </div>
    );
  }

  // Handle single data point
  if (data.length === 1) {
    return (
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className={className}
        style={{ width, height }}
        aria-label="Trend sparkline with single data point"
      >
        <circle
          cx={width / 2}
          cy={height / 2}
          r={3}
          fill="#3b82f6"
        />
      </svg>
    );
  }

  // Calculate min/max for normalization
  const scores = data.map((d) => d.score);
  const min = Math.min(...scores);
  const max = Math.max(...scores);
  const range = max - min || 1; // Avoid division by zero

  // Calculate SVG points (data is newest-first, so reverse for left-to-right)
  const reversedData = [...data].reverse();
  const points = reversedData.map((d, i) => ({
    x: (i / (reversedData.length - 1)) * width,
    y: height - 2 - ((d.score - min) / range) * (height - 4), // 2px padding
  }));

  // Build SVG path
  const pathD = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
    .join(" ");

  // Determine trend direction (compare first and last in original order)
  // data[0] is newest, data[data.length-1] is oldest
  const isUptrend = data[0].score > data[data.length - 1].score;
  const isFlat = Math.abs(data[0].score - data[data.length - 1].score) < 1;

  // Color based on trend direction
  const lineColor = isFlat ? "#6b7280" : isUptrend ? "#22c55e" : "#ef4444"; // gray-500 / green-500 / red-500

  // Today's point is the last point in the reversed array (rightmost)
  const todayPoint = points[points.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      style={{ width, height }}
      aria-label={`Trend sparkline showing ${isUptrend ? "upward" : isFlat ? "flat" : "downward"} trend`}
    >
      {/* Trend line */}
      <path
        d={pathD}
        fill="none"
        stroke={lineColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Today's marker */}
      {highlightToday && todayPoint && (
        <circle
          cx={todayPoint.x}
          cy={todayPoint.y}
          r="3"
          fill={lineColor}
          stroke="white"
          strokeWidth="1"
        />
      )}
    </svg>
  );
}

/** Skeleton loading state for TrendSparkline */
export function TrendSparklineSkeleton({
  width = 120,
  height = 24,
  className = "",
}: {
  width?: number;
  height?: number;
  className?: string;
}) {
  return (
    <div
      className={`bg-gray-200 rounded animate-pulse ${className}`}
      style={{ width, height }}
    />
  );
}

export default TrendSparkline;
