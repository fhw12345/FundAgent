/**
 * Portfolio Dashboard — Alipay-style fund holdings management.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import {
  TrendingUp,
  Camera,
  Plus,
  RefreshCw,
  DollarSign,
  X,
} from "lucide-react";
import HeroCard from "../components/portfolio/HeroCard";
import FundCard from "../components/portfolio/FundCard";
import AddHoldingModal from "../components/portfolio/AddHoldingModal";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

const headers = { "Content-Type": "application/json" };

interface FundSummary {
  fund_code: string;
  fund_name: string;
  total_shares: number;
  total_cost: number;
  avg_cost: number;
  realized_pnl: number;
  current_nav?: number;
  market_value?: number;
  unrealized_pnl?: number;
  total_return_pct?: number;
  today_est_pct?: number | null;
  today_est_pnl?: number | null;
  sectors?: { name: string; change_pct: number }[];
}

interface SnapshotHolding {
  fund_code: string;
  fund_name: string;
  shares: number | null;
  nav: number | null;
  market_value: number | null;
  return_pct: number | null;
  today_est_pct?: number | null;
  today_est_pnl?: number | null;
  sectors?: { name: string; change_pct: number }[];
}

export default function PortfolioDashboard() {
  const [summaries, setSummaries] = useState<FundSummary[]>([]);
  const [pendingCount, setPendingCount] = useState(0);
  const [todayTotalEstPnl, setTodayTotalEstPnl] = useState<number | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotHolding[]>([]);
  const [snapshotMeta, setSnapshotMeta] = useState<{ source: string | null; updated_at: string | null }>({
    source: null,
    updated_at: null,
  });
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, snapRes] = await Promise.all([
        fetch(`${API_BASE}/api/transactions/summary`, { headers }),
        fetch(`${API_BASE}/api/portfolio`, { headers }),
      ]);
      const sumData = await sumRes.json();
      const snapData = await snapRes.json();
      setSummaries(sumData.funds || []);
      setPendingCount(sumData.pending_count || 0);
      setTodayTotalEstPnl(sumData.today_total_est_pnl ?? snapData.today_total_est_pnl ?? null);
      setSnapshot(snapData.holdings || []);
      setSnapshotMeta({ source: snapData.source, updated_at: snapData.updated_at });
    } catch (e: unknown) {
      setError(`加载失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Merge transaction-derived summaries (priority) with snapshot fallback
  const mergedHoldings = (() => {
    const codes = new Set([...summaries.map((s) => s.fund_code), ...snapshot.map((s) => s.fund_code)]);
    return Array.from(codes).map((code) => {
      const sum = summaries.find((s) => s.fund_code === code);
      const snap = snapshot.find((s) => s.fund_code === code);
      const fund_name = sum?.fund_name || snap?.fund_name || "";
      const market_value = sum?.market_value ?? snap?.market_value ?? 0;
      const return_pct = sum?.total_return_pct ?? snap?.return_pct ?? null;
      const unrealized_pnl = sum?.unrealized_pnl ?? null;
      const realized_pnl = sum?.realized_pnl ?? 0;
      const total_cost = sum?.total_cost ?? null;
      const current_nav = sum?.current_nav ?? snap?.nav ?? null;
      const has_tx = !!sum;
      const today_est_pct = sum?.today_est_pct ?? snap?.today_est_pct ?? null;
      const today_est_pnl = sum?.today_est_pnl ?? snap?.today_est_pnl ?? null;
      const sectors = sum?.sectors ?? snap?.sectors ?? [];
      return {
        fund_code: code,
        fund_name,
        market_value,
        return_pct,
        unrealized_pnl,
        realized_pnl,
        total_cost,
        current_nav,
        has_tx,
        today_est_pct,
        today_est_pnl,
        sectors,
      };
    }).sort((a, b) => b.market_value - a.market_value);
  })();

  const totalAssets = mergedHoldings.reduce((sum, h) => sum + (h.market_value || 0), 0);
  const totalUnrealized = mergedHoldings.reduce((sum, h) => sum + (h.unrealized_pnl || 0), 0);
  const totalRealized = mergedHoldings.reduce((sum, h) => sum + (h.realized_pnl || 0), 0);
  const totalCost = mergedHoldings.reduce((sum, h) => sum + (h.total_cost || 0), 0);
  const totalReturnPct = totalCost > 0 ? ((totalUnrealized + totalRealized) / totalCost) * 100 : 0;

  const handleScreenshot = async (file: File) => {
    setImporting(true);
    setError(null);
    try {
      const reader = new FileReader();
      const base64 = await new Promise<string>((resolve, reject) => {
        reader.onload = () => resolve((reader.result as string).split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
      const res = await fetch(`${API_BASE}/api/portfolio/import-screenshot`, {
        method: "POST",
        headers,
        body: JSON.stringify({ image_base64: base64 }),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setSuccess(`成功导入 ${data.imported_count} 只基金`);
      void refresh();
    } catch (e: unknown) {
      setError(`截图导入失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
    }
  };

  const handleDailyAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/daily-analysis`, {
        method: "POST",
        headers,
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setSuccess(`已启动分析 ${data.fund_count} 只基金，请到「AI 对话」查看结果`);
    } catch (e: unknown) {
      setError(`分析启动失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto pb-12">
      {/* ── Hero card: total assets ── */}
      <HeroCard
        totalAssets={totalAssets}
        todayTotalEstPnl={todayTotalEstPnl}
        totalUnrealized={totalUnrealized}
        totalRealized={totalRealized}
        totalReturnPct={totalReturnPct}
        loading={loading}
        onRefresh={() => void refresh()}
      />

      {pendingCount > 0 && (
        <div className="mx-4 mt-3 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl px-4 py-2.5 flex items-center gap-2 text-sm">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse shrink-0" />
          <span className="text-amber-900 font-medium">{pendingCount} 笔待确认</span>
          <span className="text-amber-700 text-xs flex-1">
            T+1 确认后会自动并入持仓
          </span>
        </div>
      )}

      {/* ── Quick actions ── */}
      <div className="grid grid-cols-3 gap-3 mt-6 px-4">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={importing}
          className="flex flex-col items-center gap-1 p-4 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md hover:border-blue-200 transition-all disabled:opacity-50"
        >
          <div className="w-10 h-10 bg-gradient-to-br from-blue-100 to-blue-200 rounded-xl flex items-center justify-center">
            {importing ? <RefreshCw className="w-5 h-5 text-blue-600 animate-spin" /> : <Camera className="w-5 h-5 text-blue-600" />}
          </div>
          <span className="text-xs font-medium text-gray-700">截图导入</span>
        </button>
        <button
          onClick={() => setShowAddModal(true)}
          className="flex flex-col items-center gap-1 p-4 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md hover:border-purple-200 transition-all"
        >
          <div className="w-10 h-10 bg-gradient-to-br from-purple-100 to-purple-200 rounded-xl flex items-center justify-center">
            <Plus className="w-5 h-5 text-purple-600" />
          </div>
          <span className="text-xs font-medium text-gray-700">添加持仓</span>
        </button>
        <button
          onClick={() => void handleDailyAnalysis()}
          disabled={analyzing || mergedHoldings.length === 0}
          className="flex flex-col items-center gap-1 p-4 bg-white rounded-2xl shadow-sm border border-gray-100 hover:shadow-md hover:border-emerald-200 transition-all disabled:opacity-50"
        >
          <div className="w-10 h-10 bg-gradient-to-br from-emerald-100 to-emerald-200 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-5 h-5 text-emerald-600" />
          </div>
          <span className="text-xs font-medium text-gray-700">{analyzing ? "分析中" : "AI 分析"}</span>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void handleScreenshot(file);
          }}
        />
      </div>

      {/* ── Toasts ── */}
      {error && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-start justify-between gap-2">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
      {success && (
        <div className="mx-4 mt-4 bg-emerald-50 border border-emerald-200 text-emerald-700 px-4 py-3 rounded-xl text-sm flex items-start justify-between gap-2">
          <span>{success}</span>
          <button onClick={() => setSuccess(null)} className="shrink-0">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ── Holdings list ── */}
      <div className="mt-6 px-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-base font-bold text-gray-900">持仓基金 ({mergedHoldings.length})</h3>
          {snapshotMeta.source && (
            <span className="text-xs text-gray-400">
              {snapshotMeta.source === "screenshot" ? "📸 截图导入" : "✏️ 手动添加"}
            </span>
          )}
        </div>

        {mergedHoldings.length === 0 ? (
          <div className="bg-white rounded-2xl p-12 text-center border border-gray-100">
            <div className="w-16 h-16 mx-auto mb-3 bg-gray-50 rounded-2xl flex items-center justify-center">
              <DollarSign className="w-8 h-8 text-gray-300" />
            </div>
            <p className="text-gray-500 font-medium">还没有持仓</p>
            <p className="text-sm text-gray-400 mt-1">通过截图或添加交易记录来导入</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {mergedHoldings.map((h) => (
              <FundCard key={h.fund_code} holding={h} />
            ))}
          </div>
        )}
      </div>

      {showAddModal && (
        <AddHoldingModal
          onClose={() => setShowAddModal(false)}
          onAdded={() => {
            setShowAddModal(false);
            void refresh();
          }}
        />
      )}
    </div>
  );
}
