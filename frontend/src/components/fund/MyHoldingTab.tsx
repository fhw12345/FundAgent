import NavChart, { type NAVPoint } from "./NavChart";
import TransactionList from "./TransactionList";

export interface FundHoldingSummary {
  total_shares: number;
  total_cost: number;
  market_value?: number;
  unrealized_pnl?: number;
  realized_pnl?: number;
  total_return_pct?: number;
}

interface Props {
  fundCode: string;
  summary: FundHoldingSummary | null;
  navHistory: NAVPoint[];
}

export default function MyHoldingTab({ fundCode, summary, navHistory }: Props) {
  const totalReturn =
    (summary?.unrealized_pnl ?? 0) + (summary?.realized_pnl ?? 0);
  const isUp = totalReturn >= 0;
  const colorClass = isUp ? "text-red-600" : "text-emerald-600";

  return (
    <div className="space-y-4">
      {/* Holding summary */}
      {summary && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-4">持仓概览</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-400 mb-1">持有份额</div>
              <div className="font-semibold text-gray-900">
                {summary.total_shares.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">持有成本</div>
              <div className="font-semibold text-gray-900">
                ¥{summary.total_cost.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">当前市值</div>
              <div className="font-semibold text-gray-900">
                ¥{(summary.market_value ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">累计收益</div>
              <div className={`font-semibold ${colorClass}`}>
                {isUp ? "+" : ""}¥{totalReturn.toFixed(2)}
                {summary.total_return_pct != null && (
                  <span className="text-xs ml-1">
                    ({isUp ? "+" : ""}
                    {summary.total_return_pct.toFixed(2)}%)
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* NAV chart */}
      {navHistory.length > 0 && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-2">单位净值走势</h3>
          <NavChart points={navHistory} defaultRange="month" />
        </div>
      )}

      {/* Transactions */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-1">历史交易</h3>
        <TransactionList fundCode={fundCode} />
      </div>
    </div>
  );
}
