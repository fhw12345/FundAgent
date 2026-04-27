import {
  TrendingUp,
  TrendingDown,
  ChevronRight,
  ShoppingCart,
} from "lucide-react";

export interface FundCardHolding {
  fund_code: string;
  fund_name: string;
  market_value: number;
  return_pct: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number;
  total_cost: number | null;
  current_nav: number | null;
  has_tx: boolean;
  today_est_pct?: number | null;
  today_est_pnl?: number | null;
  sectors?: { name: string; change_pct: number }[];
}

interface Props {
  holding: FundCardHolding;
}

export default function FundCard({ holding }: Props) {
  const isUp = (holding.return_pct ?? 0) >= 0;
  const colorClass = isUp ? "text-red-600" : "text-emerald-600";
  const todayPct = holding.today_est_pct;
  const todayPnl = holding.today_est_pnl;
  const todayUp = (todayPct ?? 0) >= 0;
  const todayColor = todayUp ? "text-red-600" : "text-emerald-600";
  const sectors = holding.sectors ?? [];

  const openDetail = () => {
    const w = window as unknown as { openFundDetail?: (code: string) => void };
    w.openFundDetail?.(holding.fund_code);
  };

  return (
    <button
      type="button"
      onClick={openDetail}
      className="w-full text-left bg-white rounded-2xl p-4 shadow-sm border border-gray-100 hover:shadow-md hover:border-gray-200 transition-all cursor-pointer group"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-500">{holding.fund_code}</span>
            {holding.has_tx && (
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded">
                已建仓
              </span>
            )}
          </div>
          <h4 className="font-semibold text-gray-900 truncate">
            {holding.fund_name || "未知基金"}
          </h4>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 group-hover:translate-x-0.5 transition-all" />
      </div>

      {/* Data row: today estimate (left, big) | return % (middle) | market value (right, small) */}
      <div className="grid grid-cols-3 gap-3 items-end">
        <div>
          <div className="text-[11px] text-gray-400 mb-0.5">当日估算</div>
          {todayPct != null ? (
            <div>
              <div className={`text-xl font-bold leading-tight ${todayColor}`}>
                {todayUp ? "+" : ""}
                {todayPct.toFixed(2)}%
              </div>
              {todayPnl != null && (
                <div className={`text-[11px] font-medium mt-0.5 ${todayColor}`}>
                  {todayUp ? "+" : ""}
                  ¥{todayPnl.toFixed(2)}
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-sm">暂无</div>
          )}
        </div>

        <div className="text-center">
          <div className="text-[11px] text-gray-400 mb-0.5">持有收益率</div>
          <div className={`font-bold ${colorClass} flex items-center justify-center gap-0.5`}>
            {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            {holding.return_pct != null
              ? `${isUp ? "+" : ""}${holding.return_pct.toFixed(2)}%`
              : "-"}
          </div>
        </div>

        <div className="text-right">
          <div className="text-[11px] text-gray-400 mb-0.5">持仓市值</div>
          <div className="text-sm font-semibold text-gray-700">
            {holding.market_value.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Sectors */}
      {sectors.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-50 flex items-center gap-1.5 flex-wrap">
          <span className="text-[10px] text-gray-400">关联板块</span>
          {sectors.map((s) => {
            const up = s.change_pct >= 0;
            return (
              <span
                key={s.name}
                className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                  up ? "bg-red-50 text-red-600" : "bg-emerald-50 text-emerald-600"
                }`}
              >
                {s.name} {up ? "+" : ""}
                {s.change_pct.toFixed(2)}%
              </span>
            );
          })}
        </div>
      )}

      {/* Footer: cost / unrealized */}
      {holding.has_tx && (
        <div className="mt-3 pt-3 border-t border-gray-50 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-gray-500">
            <span>
              成本{" "}
              <span className="text-gray-700">{holding.total_cost?.toFixed(2)}</span>
            </span>
            <span>
              持有{" "}
              <span className={colorClass}>
                {(holding.unrealized_pnl ?? 0) >= 0 ? "+" : ""}
                {holding.unrealized_pnl?.toFixed(2)}
              </span>
            </span>
          </div>
          <div className="flex items-center gap-1 text-blue-600">
            <ShoppingCart className="w-3 h-3" />
            <span>交易</span>
          </div>
        </div>
      )}
    </button>
  );
}
