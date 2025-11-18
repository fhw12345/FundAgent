/**
 * Portfolio summary component showing aggregated metrics.
 *
 * Displays total cost basis, market value, and P/L across all holdings.
 */

import { useTranslation } from "react-i18next";
import type { PortfolioSummary } from "../../types/portfolio";
import { formatPL, getPLColor } from "../../services/portfolioApi";

interface PortfolioSummaryProps {
  summary: PortfolioSummary | undefined;
  isLoading: boolean;
}

export function PortfolioSummaryCard({
  summary,
  isLoading,
}: PortfolioSummaryProps) {
  const { t } = useTranslation(['portfolio', 'common']);

  if (isLoading) {
    return (
      <div className="bg-white p-6 rounded-lg shadow animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i}>
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-2"></div>
              <div className="h-6 bg-gray-200 rounded w-full"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!summary || summary.holdings_count === 0) {
    return (
      <div className="bg-white p-6 rounded-lg shadow">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          {t('portfolio:summary.title')}
        </h2>
        <p className="text-gray-500">{t('portfolio:summaryCard.noHoldingsDisplay')}</p>
      </div>
    );
  }

  const plColor = getPLColor(summary.total_unrealized_pl);
  const colorClass =
    plColor === "green"
      ? "text-green-600"
      : plColor === "red"
        ? "text-red-600"
        : "text-gray-600";

  return (
    <div className="bg-white p-6 rounded-lg shadow">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        {t('portfolio:summary.title')}
      </h2>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
        {/* Holdings Count */}
        <div>
          <p className="text-sm text-gray-500 mb-1">{t('portfolio:summaryCard.holdings')}</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary.holdings_count}
          </p>
        </div>

        {/* Total Cost Basis */}
        <div>
          <p className="text-sm text-gray-500 mb-1">{t('portfolio:summaryCard.costBasis')}</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary.total_cost_basis !== null
              ? `$${summary.total_cost_basis.toFixed(2)}`
              : "N/A"}
          </p>
        </div>

        {/* Total Market Value */}
        <div>
          <p className="text-sm text-gray-500 mb-1">{t('portfolio:summaryCard.marketValue')}</p>
          <p className="text-2xl font-bold text-gray-900">
            {summary.total_market_value !== null
              ? `$${summary.total_market_value.toFixed(2)}`
              : "N/A"}
          </p>
        </div>

        {/* Total Unrealized Gain/Loss */}
        <div>
          <p className="text-sm text-gray-500 mb-1 flex items-center gap-1">
            {t('portfolio:summary.totalGain')}
            <span className="text-gray-400 text-xs" title="Unrealized profit/loss across all holdings">
              ⓘ
            </span>
          </p>
          <p className={`text-2xl font-bold ${colorClass}`}>
            {summary.total_unrealized_pl === null ? (
              <span className="text-gray-400 text-base">{t('portfolio:summaryCard.calculating')}</span>
            ) : (
              formatPL(summary.total_unrealized_pl, summary.total_unrealized_pl_pct)
            )}
          </p>
        </div>
      </div>

      {/* Auto-refresh indicator */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-400 flex items-center">
          <span className="inline-block w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse"></span>
          {t('portfolio:footer.priceUpdates')}
        </p>
      </div>
    </div>
  );
}
