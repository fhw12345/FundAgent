import React from 'react';
import type { Holding, PortfolioSummary } from '../../types/portfolio';

interface PortfolioSummaryTableProps {
  holdings: Holding[];
  summary: PortfolioSummary;
}

export function PortfolioSummaryTable({ holdings, summary }: PortfolioSummaryTableProps) {
  // Calculate totals
  const totalMarketValue = summary.total_market_value || 0;
  const totalPL = summary.total_unrealized_pl || 0;
  const totalPLPct = summary.total_unrealized_pl_pct || 0;

  // Helper to format currency
  const formatCurrency = (value: number): string => {
    return `$${value.toFixed(2)}`;
  };

  // Helper to format percentage
  const formatPercentage = (value: number): string => {
    return `${value.toFixed(2)}%`;
  };

  // Helper to get color class for P/L
  const getPLColorClass = (value: number): string => {
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  // Helper to get emoji for P/L
  const getPLEmoji = (value: number): string => {
    return value >= 0 ? '🟢' : '🔴';
  };

  if (holdings.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500">
        <p>No positions to display</p>
        <p className="text-sm mt-2">Start trading to see your portfolio here</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h2 className="text-xl font-bold mb-4">Portfolio Holdings</h2>

      <div className="overflow-x-auto">
        <table className="w-full font-mono text-sm border-collapse">
          <thead>
            <tr className="border-b-2 border-gray-300">
              <th className="text-left py-2 px-2">Symbol</th>
              <th className="text-right py-2 px-2">Qty</th>
              <th className="text-right py-2 px-2">Avg Price</th>
              <th className="text-right py-2 px-2">Current</th>
              <th className="text-right py-2 px-2">Market Value</th>
              <th className="text-right py-2 px-2">P/L</th>
              <th className="text-right py-2 px-2">P/L%</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((holding) => {
              const pl = holding.unrealized_pl || 0;
              const plPct = holding.unrealized_pl_pct || 0;

              return (
                <tr
                  key={holding.symbol}
                  className="border-b border-gray-200 hover:bg-gray-50"
                >
                  <td className="py-2 px-2 font-bold">{holding.symbol}</td>
                  <td className="text-right py-2 px-2">{holding.quantity}</td>
                  <td className="text-right py-2 px-2">
                    {formatCurrency(holding.avg_price)}
                  </td>
                  <td className="text-right py-2 px-2">
                    {holding.current_price ? formatCurrency(holding.current_price) : '-'}
                  </td>
                  <td className="text-right py-2 px-2">
                    {holding.market_value ? formatCurrency(holding.market_value) : '-'}
                  </td>
                  <td className={`text-right py-2 px-2 ${getPLColorClass(pl)}`}>
                    {getPLEmoji(pl)} {formatCurrency(pl)}
                  </td>
                  <td className={`text-right py-2 px-2 ${getPLColorClass(plPct)}`}>
                    {formatPercentage(plPct)}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot className="border-t-2 border-gray-300 font-bold bg-gray-50">
            <tr>
              <td colSpan={4} className="py-2 px-2">TOTAL</td>
              <td className="text-right py-2 px-2">
                {formatCurrency(totalMarketValue)}
              </td>
              <td className={`text-right py-2 px-2 ${getPLColorClass(totalPL)}`}>
                {formatCurrency(totalPL)}
              </td>
              <td className={`text-right py-2 px-2 ${getPLColorClass(totalPLPct)}`}>
                {formatPercentage(totalPLPct)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Summary stats below table */}
      <div className="mt-6 grid grid-cols-2 gap-4 text-sm">
        <div className="bg-blue-50 p-3 rounded">
          <p className="text-gray-600">Total Cost Basis</p>
          <p className="text-lg font-bold text-blue-600">
            {formatCurrency(summary.total_cost_basis || 0)}
          </p>
        </div>
        <div className="bg-green-50 p-3 rounded">
          <p className="text-gray-600">Total Market Value</p>
          <p className="text-lg font-bold text-green-600">
            {formatCurrency(totalMarketValue)}
          </p>
        </div>
      </div>
    </div>
  );
}
