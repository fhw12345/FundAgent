import { useState } from "react";
import { RefreshCw, ChevronDown } from "lucide-react";

interface Props {
  totalAssets: number;
  todayTotalEstPnl: number | null;
  totalUnrealized: number;
  totalRealized: number;
  totalReturnPct: number;
  loading: boolean;
  onRefresh: () => void;
}

export default function HeroCard({
  totalAssets,
  todayTotalEstPnl,
  totalUnrealized,
  totalRealized,
  totalReturnPct,
  loading,
  onRefresh,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-red-500 via-rose-500 to-red-600 text-white p-6 sm:p-8 sm:rounded-3xl sm:mt-4 mx-0 sm:mx-4 shadow-xl shadow-red-500/30">
      <div className="absolute -right-12 -top-12 w-48 h-48 bg-white/10 rounded-full" />
      <div className="absolute -right-4 -bottom-16 w-40 h-40 bg-white/5 rounded-full" />
      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-white/80">基金总资产 (元)</span>
          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-1.5 hover:bg-white/20 rounded-lg transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        <div className="text-4xl sm:text-5xl font-bold tracking-tight mb-1">
          {totalAssets.toFixed(2)}
        </div>

        {todayTotalEstPnl != null && (
          <div className="text-sm text-white/90 mb-1">
            今日估算 {todayTotalEstPnl >= 0 ? "+" : ""}
            ¥{todayTotalEstPnl.toFixed(2)}
          </div>
        )}

        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm">
            <span className="text-white/70 text-xs mr-2">持有收益率</span>
            <span className="font-semibold">
              {totalReturnPct >= 0 ? "+" : ""}
              {totalReturnPct.toFixed(2)}%
            </span>
          </div>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs text-white/80 hover:text-white"
          >
            {expanded ? "收起明细" : "展开明细"}
            <ChevronDown
              className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        </div>

        {expanded && (
          <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/20 text-sm">
            <div>
              <div className="text-white/70 text-xs mb-1">未实现盈亏</div>
              <div className="font-semibold">
                {totalUnrealized >= 0 ? "+" : ""}
                {totalUnrealized.toFixed(2)}
              </div>
            </div>
            <div className="w-px h-8 bg-white/20" />
            <div>
              <div className="text-white/70 text-xs mb-1">已实现盈亏</div>
              <div className="font-semibold">
                {totalRealized >= 0 ? "+" : ""}
                {totalRealized.toFixed(2)}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
