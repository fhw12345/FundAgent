/**
 * MetricCard component for displaying individual metrics.
 * Expandable card with score, status, trend sparkline, and rich explanation.
 */

import { ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { InsightMetric, TrendDataPoint } from "../../types/insights";
import { ExpandedTrendChart, ExpandedTrendChartSkeleton } from "./ExpandedTrendChart";
import { ExplanationPanel, ExplanationPreview } from "./ExplanationPanel";
import { ScoreGauge } from "./ScoreGauge";
import { StatusBadge } from "./StatusBadge";
import { SwipeContainer } from "./SwipeContainer";
import { TrendSparkline, TrendSparklineSkeleton } from "./TrendSparkline";

interface MetricCardProps {
  metric: InsightMetric;
  isExpanded: boolean;
  onToggle: () => void;
  /** Optional trend data for sparkline visualization */
  trendData?: TrendDataPoint[];
  /** Whether trend data is loading */
  trendLoading?: boolean;
  /** Callback when user swipes for more history */
  onLoadMoreHistory?: () => void;
}

export function MetricCard({
  metric,
  isExpanded,
  onToggle,
  trendData,
  trendLoading = false,
  onLoadMoreHistory,
}: MetricCardProps) {
  const { t } = useTranslation(["insights"]);

  // Render sparkline section
  const renderSparkline = () => {
    if (trendLoading) {
      return <TrendSparklineSkeleton width={100} height={20} className="mt-2" />;
    }
    if (trendData && trendData.length > 0) {
      return (
        <SwipeContainer
          onSwipeLeft={onLoadMoreHistory}
          showHint={!!onLoadMoreHistory}
          className="mt-2"
        >
          <TrendSparkline
            data={trendData}
            highlightToday={true}
            width={100}
            height={20}
          />
        </SwipeContainer>
      );
    }
    return null;
  };

  return (
    <div
      className={`bg-white/60 border rounded-xl overflow-hidden transition-all duration-300 ${
        isExpanded
          ? "border-blue-200 shadow-lg shadow-blue-100/50"
          : "border-gray-200/50 hover:shadow-md hover:border-gray-300/50"
      }`}
    >
      {/* Header - always visible */}
      <button
        onClick={onToggle}
        aria-expanded={isExpanded}
        aria-controls={`metric-content-${metric.id}`}
        className="w-full p-4 flex items-center justify-between text-left hover:bg-gray-50/50 transition-colors group focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-inset"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h4
              id={`metric-header-${metric.id}`}
              className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors"
            >
              {metric.name}
            </h4>
            <StatusBadge status={metric.status} size="sm" />
          </div>
          <ExplanationPreview summary={metric.explanation.summary} />
          {/* Trend sparkline */}
          {renderSparkline()}
        </div>
        <div className="flex items-center gap-4 ml-4 flex-shrink-0">
          <ScoreGauge score={metric.score} status={metric.status} />
          <div
            className={`transition-transform duration-300 ${isExpanded ? "rotate-90" : ""}`}
          >
            <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-blue-500 transition-colors" />
          </div>
        </div>
      </button>

      {/* Expanded content with smooth animation */}
      <div
        id={`metric-content-${metric.id}`}
        role="region"
        aria-labelledby={`metric-header-${metric.id}`}
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isExpanded ? "max-h-[800px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-4 pb-4 border-t border-gray-100 pt-4 space-y-4">
          {/* Expanded trend chart - full width */}
          {trendLoading ? (
            <ExpandedTrendChartSkeleton height={120} />
          ) : trendData && trendData.length > 1 ? (
            <div className="bg-gray-50/50 rounded-lg p-3 -mx-1">
              <ExpandedTrendChart
                data={trendData}
                title={t("insights:trend.score_history")}
                height={120}
              />
            </div>
          ) : null}

          {/* Explanation panel */}
          <ExplanationPanel
            explanation={metric.explanation}
            dataSources={metric.data_sources}
          />
        </div>
      </div>
    </div>
  );
}

/** Skeleton loading state for MetricCard */
export function MetricCardSkeleton() {
  return (
    <div className="bg-white/60 border border-gray-200/50 rounded-xl p-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-5 w-32 bg-gray-200 rounded" />
            <div className="h-5 w-16 bg-gray-200 rounded-full" />
          </div>
          <div className="h-4 w-3/4 bg-gray-200 rounded" />
        </div>
        <div className="flex items-center gap-4">
          <div className="w-24 h-3 bg-gray-200 rounded-full" />
          <div className="w-8 h-4 bg-gray-200 rounded" />
          <div className="w-5 h-5 bg-gray-200 rounded" />
        </div>
      </div>
    </div>
  );
}

export default MetricCard;
