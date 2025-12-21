/**
 * StatusBadge component for displaying metric status.
 * Color-coded pill showing risk/status level.
 */

import { useTranslation } from "react-i18next";
import {
  getStatusBgColor,
  getStatusColor,
} from "../../services/insightsApi";
import type { MetricStatus } from "../../types/insights";

interface StatusBadgeProps {
  status: MetricStatus;
  size?: "sm" | "md" | "lg";
}

/** Get size classes for badge */
function getSizeClasses(size: "sm" | "md" | "lg"): string {
  switch (size) {
    case "sm":
      return "px-2 py-0.5 text-xs";
    case "lg":
      return "px-4 py-2 text-sm";
    default:
      return "px-2.5 py-1 text-xs";
  }
}

export function StatusBadge({ status, size = "md" }: StatusBadgeProps) {
  const { t } = useTranslation(["insights"]);
  const bgColor = getStatusBgColor(status);
  const textColor = getStatusColor(status);
  const sizeClasses = getSizeClasses(size);

  return (
    <span
      className={`font-medium rounded-full ${bgColor} ${textColor} ${sizeClasses} transition-colors duration-200`}
    >
      {t(`insights:status.${status}`)}
    </span>
  );
}

export default StatusBadge;
