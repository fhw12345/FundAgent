import NavChart, { type NAVPoint } from "./NavChart";

export interface TopHolding {
  rank: number;
  stock_code: string;
  stock_name: string;
  ratio_pct: number;
}

interface Props {
  navHistory: NAVPoint[];
  topHoldings: TopHolding[];
  holdingsQuarter?: string;
  basicInfo: Record<string, string>;
}

export default function FundInfoTab({
  navHistory,
  topHoldings,
  holdingsQuarter,
  basicInfo,
}: Props) {
  return (
    <div className="space-y-4">
      {navHistory.length > 0 && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-2">单位净值走势</h3>
          <NavChart points={navHistory} defaultRange="month" />
        </div>
      )}

      {topHoldings.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">十大重仓股</h3>
            {holdingsQuarter && (
              <span className="text-xs text-gray-400">{holdingsQuarter}</span>
            )}
          </div>
          <div className="divide-y divide-gray-50">
            {topHoldings.map((h) => (
              <div key={h.rank} className="flex items-center px-5 py-3">
                <div className="w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-xs font-bold flex items-center justify-center shrink-0">
                  {h.rank}
                </div>
                <div className="ml-3 flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">
                    {h.stock_name}
                  </div>
                  <div className="text-xs text-gray-400 font-mono">{h.stock_code}</div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-gray-900">
                    {h.ratio_pct.toFixed(2)}%
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(basicInfo).length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50">
            <h3 className="font-semibold text-gray-900">基金概况</h3>
          </div>
          <div className="divide-y divide-gray-50">
            {Object.entries(basicInfo).map(([k, v]) => (
              <div key={k} className="flex justify-between px-5 py-3 text-sm">
                <span className="text-gray-500">{k}</span>
                <span className="text-gray-900 font-medium text-right ml-3 truncate max-w-[60%]">
                  {v}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
