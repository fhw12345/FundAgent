/**
 * ScoreGauge component for visual score display.
 * Shows a horizontal progress bar with animated fill based on score.
 */

import { formatScore, getStatusColor } from "../../services/insightsApi";
import type { MetricStatus } from "../../types/insights";

interface ScoreGaugeProps {
  score: number;
  status: MetricStatus;
  size?: "sm" | "md" | "lg";
  showLabel?: boolean;
}

/** Get bar color based on status */
function getBarColor(status: MetricStatus): string {
  switch (status) {
    case "low":
      return "bg-green-500";
    case "normal":
      return "bg-blue-500";
    case "elevated":
      return "bg-orange-500";
    case "high":
      return "bg-red-500";
    default:
      return "bg-gray-500";
  }
}

/** Get size classes */
function getSizeClasses(size: "sm" | "md" | "lg"): {
  bar: string;
  text: string;
  width: string;
} {
  switch (size) {
    case "sm":
      return { bar: "h-2", text: "text-sm", width: "w-16" };
    case "lg":
      return { bar: "h-4", text: "text-xl", width: "w-32" };
    default:
      return { bar: "h-3", text: "text-lg", width: "w-24" };
  }
}

export function ScoreGauge({
  score,
  status,
  size = "md",
  showLabel = true,
}: ScoreGaugeProps) {
  const percentage = score < 0 ? 0 : Math.min(100, score);
  const statusColor = getStatusColor(status);
  const barColor = getBarColor(status);
  const sizeClasses = getSizeClasses(size);

  return (
    <div className="flex items-center gap-3">
      <div
        role="progressbar"
        aria-valuenow={score < 0 ? 0 : Math.round(score)}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Score: ${formatScore(score)} - ${status}`}
        className={`relative ${sizeClasses.width} ${sizeClasses.bar} bg-gray-200 rounded-full overflow-hidden`}
      >
        <div
          className={`absolute left-0 top-0 h-full rounded-full transition-all duration-700 ease-out ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      {showLabel && (
        <span className={`font-bold ${sizeClasses.text} ${statusColor}`}>
          {formatScore(score)}
        </span>
      )}
    </div>
  );
}

export default ScoreGauge;
