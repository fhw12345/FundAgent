/**
 * Fund Detail Page — hero + tabs (我的持仓 / 基金资料).
 */

import { useState, useEffect } from "react";
import { ArrowLeft, TrendingUp, TrendingDown, RefreshCw, Sparkles } from "lucide-react";
import MyHoldingTab, { type FundHoldingSummary } from "../components/fund/MyHoldingTab";
import FundInfoTab, { type TopHolding } from "../components/fund/FundInfoTab";
import { type NAVPoint } from "../components/fund/NavChart";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

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

interface SummaryFund extends FundHoldingSummary {
  fund_code: string;
}

interface Props {
  fundCode: string;
  onBack: () => void;
  onAnalyze?: (code: string) => void;
}

type Tab = "holding" | "info";

export default function FundDetailPage({ fundCode, onBack, onAnalyze }: Props) {
  const [data, setData] = useState<FundDetail | null>(null);
  const [summary, setSummary] = useState<FundHoldingSummary | null>(null);
  const [hasHolding, setHasHolding] = useState(false);
  const [tab, setTab] = useState<Tab>("info"); // safe default; overridden once summary loads
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch fund detail
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${API_BASE}/api/funds/${fundCode}`, {
      headers: { "Content-Type": "application/json" },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json() as Promise<FundDetail>;
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

  // Fetch per-fund summary (decides whether 我的持仓 tab shows)
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/transactions/summary`, {
      headers: { "Content-Type": "application/json" },
    })
      .then((r) => (r.ok ? (r.json() as Promise<{ funds?: SummaryFund[] }>) : { funds: [] as SummaryFund[] }))
      .then((d) => {
        if (cancelled) return;
        const match = d.funds?.find(
          (f) => f.fund_code === fundCode,
        );
        if (match) {
          setSummary(match);
          setHasHolding(true);
          setTab("holding");
        } else {
          setHasHolding(false);
          setTab("info");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHasHolding(false);
          setTab("info");
        }
      });
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
  const heroGradient = isUp
    ? "from-red-500 via-rose-500 to-red-600 shadow-red-500/30"
    : "from-emerald-500 via-green-500 to-emerald-600 shadow-emerald-500/30";

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

      {/* Hero */}
      <div
        className={`relative overflow-hidden bg-gradient-to-br ${heroGradient} text-white p-6 sm:p-8 sm:rounded-3xl mt-4 mx-0 sm:mx-4 shadow-xl`}
      >
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

      {/* Tabs */}
      <div className="mt-6 mx-4 flex items-center gap-1 bg-gray-50 rounded-xl p-1 max-w-xs">
        {hasHolding && (
          <button
            onClick={() => setTab("holding")}
            className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
              tab === "holding"
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            我的持仓
          </button>
        )}
        <button
          onClick={() => setTab("info")}
          className={`flex-1 px-4 py-2 text-sm font-medium rounded-lg transition-all ${
            tab === "info"
              ? "bg-white text-gray-900 shadow-sm"
              : "text-gray-500 hover:text-gray-700"
          }`}
        >
          基金资料
        </button>
      </div>

      {/* Tab content */}
      <div className="mt-4 mx-4">
        {tab === "holding" && hasHolding ? (
          <MyHoldingTab
            fundCode={fundCode}
            summary={summary}
            navHistory={data.nav_history}
          />
        ) : (
          <FundInfoTab
            navHistory={data.nav_history}
            topHoldings={data.top_holdings}
            holdingsQuarter={data.holdings_quarter}
            basicInfo={data.basic_info}
          />
        )}
      </div>
    </div>
  );
}
