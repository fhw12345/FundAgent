/**
 * Fund Detail Page — NAV chart, basic info, top holdings.
 */

import { useState, useEffect } from "react";
import { ArrowLeft, TrendingUp, TrendingDown, RefreshCw, Sparkles } from "lucide-react";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

interface NAVPoint {
  date: string;
  nav: number;
  change_pct: number;
}

interface TopHolding {
  rank: number;
  stock_code: string;
  stock_name: string;
  ratio_pct: number;
}

interface FundDetail {
  fund_code: string;
  fund_name: string;
  basic_info: Record<string, string>;
  nav_history: NAVPoint[];
  top_holdings: TopHolding[];
  holdings_quarter?: string;
  latest_nav?: number;
  latest_change_pct?: number;
  latest_date?: string;
}

interface Props {
  fundCode: string;
  onBack: () => void;
  onAnalyze?: (code: string) => void;
}

export default function FundDetailPage({ fundCode, onBack, onAnalyze }: Props) {
  const [data, setData] = useState<FundDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/funds/${fundCode}`, { headers: { "Content-Type": "application/json" } })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [fundCode]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto p-8 text-center">
        <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-3" />
        <p className="text-gray-500">加载中...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="max-w-3xl mx-auto p-4">
        <button onClick={onBack} className="flex items-center gap-1 text-gray-600 mb-4">
          <ArrowLeft className="w-4 h-4" /> 返回
        </button>
        <div className="bg-red-50 border border-red-200 text-red-700 p-4 rounded-xl">
          加载失败: {error}
        </div>
      </div>
    );
  }

  const isUp = (data.latest_change_pct ?? 0) >= 0;
  const navColorClass = isUp ? "text-red-600" : "text-emerald-600";
  const heroGradient = isUp
    ? "from-red-500 via-rose-500 to-red-600 shadow-red-500/30"
    : "from-emerald-500 via-green-500 to-emerald-600 shadow-emerald-500/30";

  const navValues = data.nav_history.map((p) => p.nav);
  const minNav = Math.min(...navValues);
  const maxNav = Math.max(...navValues);

  return (
    <div className="max-w-3xl mx-auto pb-12">
      {/* Header */}
      <div className="px-4 pt-4 flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center gap-1 px-3 py-1.5 bg-white rounded-lg border border-gray-200 hover:bg-gray-50"
        >
          <ArrowLeft className="w-4 h-4" /> <span className="text-sm">返回</span>
        </button>
        {onAnalyze && (
          <button
            onClick={() => onAnalyze(data.fund_code)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg text-sm font-medium shadow-sm hover:shadow-md"
          >
            <Sparkles className="w-4 h-4" /> AI 分析
          </button>
        )}
      </div>

      {/* Hero card */}
      <div className={`relative overflow-hidden bg-gradient-to-br ${heroGradient} text-white p-6 sm:p-8 sm:rounded-3xl mt-4 mx-0 sm:mx-4 shadow-xl`}>
        <div className="absolute -right-12 -top-12 w-48 h-48 bg-white/10 rounded-full" />
        <div className="relative">
          <div className="text-xs text-white/80 mb-1 font-mono">{data.fund_code}</div>
          <h1 className="text-xl font-bold mb-4">{data.fund_name || "未知基金"}</h1>
          <div className="flex items-end gap-3">
            <div className="text-4xl font-bold">{data.latest_nav?.toFixed(4) ?? "-"}</div>
            <div className="pb-1.5 flex items-center gap-1">
              {isUp ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
              <span className="text-lg font-semibold">
                {isUp ? "+" : ""}
                {data.latest_change_pct?.toFixed(2) ?? "-"}%
              </span>
            </div>
          </div>
          <div className="text-xs text-white/70 mt-2">单位净值 · {data.latest_date}</div>
        </div>
      </div>

      {/* NAV chart */}
      {data.nav_history.length > 0 && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100 mt-6 mx-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">单位净值走势</h3>
            <span className="text-xs text-gray-400">近 {data.nav_history.length} 个交易日</span>
          </div>
          <NavChart points={data.nav_history} minNav={minNav} maxNav={maxNav} colorClass={navColorClass} />
          <div className="grid grid-cols-2 mt-3 text-xs text-gray-500">
            <div>最低 <span className="text-gray-700 font-medium">{minNav.toFixed(4)}</span></div>
            <div className="text-right">最高 <span className="text-gray-700 font-medium">{maxNav.toFixed(4)}</span></div>
          </div>
        </div>
      )}

      {/* Top holdings */}
      {data.top_holdings.length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mt-4 mx-4 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900">十大重仓股</h3>
            <span className="text-xs text-gray-400">{data.holdings_quarter}</span>
          </div>
          <div className="divide-y divide-gray-50">
            {data.top_holdings.map((h) => (
              <div key={h.rank} className="flex items-center px-5 py-3">
                <div className="w-6 h-6 rounded-full bg-blue-50 text-blue-600 text-xs font-bold flex items-center justify-center shrink-0">
                  {h.rank}
                </div>
                <div className="ml-3 flex-1 min-w-0">
                  <div className="font-medium text-gray-900 truncate">{h.stock_name}</div>
                  <div className="text-xs text-gray-400 font-mono">{h.stock_code}</div>
                </div>
                <div className="text-right">
                  <div className="font-bold text-gray-900">{h.ratio_pct.toFixed(2)}%</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Basic info */}
      {Object.keys(data.basic_info).length > 0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 mt-4 mx-4 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-50">
            <h3 className="font-semibold text-gray-900">基金概况</h3>
          </div>
          <div className="divide-y divide-gray-50">
            {Object.entries(data.basic_info).map(([k, v]) => (
              <div key={k} className="flex justify-between px-5 py-3 text-sm">
                <span className="text-gray-500">{k}</span>
                <span className="text-gray-900 font-medium text-right ml-3 truncate max-w-[60%]">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function NavChart({ points, minNav, maxNav, colorClass }: { points: NAVPoint[]; minNav: number; maxNav: number; colorClass: string }) {
  const W = 600;
  const H = 160;
  const PAD = 10;
  const range = maxNav - minNav || 1;
  const stepX = (W - PAD * 2) / (points.length - 1 || 1);

  const path = points
    .map((p, i) => {
      const x = PAD + i * stepX;
      const y = H - PAD - ((p.nav - minNav) / range) * (H - PAD * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  const areaPath = `${path} L${(PAD + (points.length - 1) * stepX).toFixed(1)} ${H - PAD} L${PAD} ${H - PAD} Z`;
  const isUp = colorClass.includes("red");
  const strokeColor = isUp ? "#ef4444" : "#10b981";
  const fillId = isUp ? "navGradRed" : "navGradGreen";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-40">
      <defs>
        <linearGradient id="navGradRed" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ef4444" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#ef4444" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="navGradGreen" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${fillId})`} />
      <path d={path} fill="none" stroke={strokeColor} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
