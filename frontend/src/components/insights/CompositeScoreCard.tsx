/**
 * CompositeScoreCard component for displaying category composite scores.
 * Shows the weighted aggregate score with breakdown.
 */

import { useTranslation } from "react-i18next";
import { formatScore } from "../../services/insightsApi";
import type { CompositeScore } from "../../types/insights";
import { StatusBadge } from "./StatusBadge";

interface CompositeScoreCardProps {
  composite: CompositeScore;
}

export function CompositeScoreCard({ composite }: CompositeScoreCardProps) {
  const { t } = useTranslation(["insights"]);

  return (
    <div className="bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-900 rounded-xl p-6 text-white overflow-hidden relative">
      {/* Background decoration */}
      <div className="absolute inset-0 bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGRlZnM+PHBhdHRlcm4gaWQ9ImdyaWQiIHdpZHRoPSI0MCIgaGVpZ2h0PSI0MCIgcGF0dGVyblVuaXRzPSJ1c2VyU3BhY2VPblVzZSI+PHBhdGggZD0iTSAwIDEwIEwgNDAgMTAgTSAxMCAwIEwgMTAgNDAgTSAwIDIwIEwgNDAgMjAgTSAyMCAwIEwgMjAgNDAgTSAwIDMwIEwgNDAgMzAgTSAzMCAwIEwgMzAgNDAiIGZpbGw9Im5vbmUiIHN0cm9rZT0icmdiYSgyNTUsMjU1LDI1NSwwLjAzKSIgc3Ryb2tlLXdpZHRoPSIxIi8+PC9wYXR0ZXJuPjwvZGVmcz48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSJ1cmwoI2dyaWQpIi8+PC9zdmc+')] opacity-50" />

      <div className="relative">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold">
            {t("insights:category.composite_score")}
          </h3>
          <StatusBadge status={composite.status} size="md" />
        </div>

        {/* Score and interpretation */}
        <div className="flex items-center gap-8 mb-6">
          {/* Big score number */}
          <div className="relative">
            <div className="text-6xl font-bold tracking-tight">
              {formatScore(composite.score)}
            </div>
            <div className="text-xs text-blue-200 mt-1">/ 100</div>
          </div>

          {/* Interpretation */}
          <div className="flex-1">
            <p className="text-blue-100 leading-relaxed">
              {composite.interpretation}
            </p>
          </div>
        </div>

        {/* Score breakdown */}
        <div className="pt-4 border-t border-white/20">
          <div className="text-xs text-blue-200 mb-3 uppercase tracking-wider">
            Score Breakdown
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
            {Object.entries(composite.breakdown).map(([metric, contribution]) => {
              const weight = composite.weights[metric] ?? 0;
              return (
                <div key={metric} className="text-center p-3 bg-white/5 rounded-lg">
                  <div className="text-xs text-blue-200 mb-1 capitalize truncate">
                    {metric.replace(/_/g, " ")}
                  </div>
                  <div className="text-xl font-semibold mb-0.5">
                    {contribution.toFixed(1)}
                  </div>
                  <div className="text-xs text-blue-300">
                    weight: {(weight * 100).toFixed(0)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Skeleton loading state for CompositeScoreCard */
export function CompositeScoreCardSkeleton() {
  return (
    <div className="bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-900 rounded-xl p-6 animate-pulse">
      <div className="flex items-center justify-between mb-6">
        <div className="h-6 w-32 bg-white/20 rounded" />
        <div className="h-6 w-20 bg-white/20 rounded-full" />
      </div>
      <div className="flex items-center gap-8 mb-6">
        <div className="h-16 w-24 bg-white/20 rounded" />
        <div className="flex-1 space-y-2">
          <div className="h-4 w-full bg-white/20 rounded" />
          <div className="h-4 w-3/4 bg-white/20 rounded" />
        </div>
      </div>
      <div className="pt-4 border-t border-white/20">
        <div className="grid grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-white/10 rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default CompositeScoreCard;
