/**
 * Portfolio Dashboard — Alipay-style fund holdings management.
 */

import { useState, useCallback, useEffect, useRef } from "react";
import {
  TrendingUp,
  TrendingDown,
  Camera,
  Plus,
  RefreshCw,
  ChevronRight,
  ShoppingCart,
  DollarSign,
  X,
} from "lucide-react";

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
      <div className="relative overflow-hidden bg-gradient-to-br from-red-500 via-rose-500 to-red-600 text-white p-6 sm:p-8 sm:rounded-3xl sm:mt-4 mx-0 sm:mx-4 shadow-xl shadow-red-500/30">
        <div className="absolute -right-12 -top-12 w-48 h-48 bg-white/10 rounded-full" />
        <div className="absolute -right-4 -bottom-16 w-40 h-40 bg-white/5 rounded-full" />
        <div className="relative">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm text-white/80">基金总资产 (元)</span>
            <button
              onClick={() => void refresh()}
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
          <div className="flex items-center gap-4 mt-4 text-sm">
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
            <div className="w-px h-8 bg-white/20" />
            <div>
              <div className="text-white/70 text-xs mb-1">持有收益率</div>
              <div className="font-semibold">
                {totalReturnPct >= 0 ? "+" : ""}
                {totalReturnPct.toFixed(2)}%
              </div>
            </div>
          </div>
        </div>
      </div>

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

// ── Fund card ────────────────────────────────────────────────────────

interface FundCardProps {
  holding: {
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
  };
}

function FundCard({ holding }: FundCardProps) {
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
    <div
      onClick={openDetail}
      className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 hover:shadow-md hover:border-gray-200 transition-all cursor-pointer group"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-500">{holding.fund_code}</span>
            {holding.has_tx && (
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded">已建仓</span>
            )}
          </div>
          <h4 className="font-semibold text-gray-900 truncate">{holding.fund_name || "未知基金"}</h4>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 group-hover:translate-x-0.5 transition-all" />
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-xs text-gray-400 mb-0.5">持仓市值</div>
          <div className="font-bold text-gray-900">{holding.market_value.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400 mb-0.5">当日估算</div>
          {todayPct != null ? (
            <div className={`font-bold ${todayColor}`}>
              {todayUp ? "+" : ""}
              {todayPct.toFixed(2)}%
              {todayPnl != null && (
                <span className="block text-[11px] font-medium mt-0.5">
                  {todayUp ? "+" : ""}
                  ¥{todayPnl.toFixed(2)}
                </span>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-xs">暂无</div>
          )}
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-400 mb-0.5">持有收益率</div>
          <div className={`font-bold ${colorClass} flex items-center justify-end gap-0.5`}>
            {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            {holding.return_pct != null ? `${isUp ? "+" : ""}${holding.return_pct.toFixed(2)}%` : "-"}
          </div>
        </div>
      </div>

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

      {holding.has_tx && (
        <div className="mt-3 pt-3 border-t border-gray-50 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-gray-500">
            <span>
              成本 <span className="text-gray-700">{holding.total_cost?.toFixed(2)}</span>
            </span>
            <span>
              持有 <span className={colorClass}>
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
    </div>
  );
}

// ── Add holding modal ────────────────────────────────────────────────

function AddHoldingModal({ onClose, onAdded }: { onClose: () => void; onAdded: () => void }) {
  const [form, setForm] = useState({ fund_code: "", market_value: "", return_pct: "" });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!form.fund_code.match(/^\d{6}$/)) {
      setErr("基金代码须为6位数字");
      return;
    }
    setSubmitting(true);
    try {
      // Get current portfolio first to merge
      const cur = await fetch(`${API_BASE}/api/portfolio`, { headers });
      const curData = await cur.json();
      const existing = curData.holdings || [];
      if (existing.some((h: { fund_code: string }) => h.fund_code === form.fund_code)) {
        throw new Error("该基金已在持仓中");
      }
      const newHoldings = [
        ...existing,
        {
          fund_code: form.fund_code,
          fund_name: "",
          shares: null,
          nav: null,
          market_value: form.market_value ? parseFloat(form.market_value) : null,
          return_pct: form.return_pct ? parseFloat(form.return_pct) : null,
        },
      ];
      const res = await fetch(`${API_BASE}/api/portfolio`, {
        method: "PUT",
        headers,
        body: JSON.stringify({ holdings: newHoldings }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      onAdded();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
      <div className="bg-white rounded-t-3xl sm:rounded-3xl shadow-xl w-full sm:max-w-md p-6 animate-in slide-in-from-bottom">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold">添加持仓</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        {err && <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-lg mb-4">{err}</div>}
        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">基金代码</label>
            <input
              type="text"
              value={form.fund_code}
              onChange={(e) => setForm({ ...form, fund_code: e.target.value })}
              maxLength={6}
              placeholder="如 110011"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">持仓金额 (元)</label>
            <input
              type="number"
              step="0.01"
              value={form.market_value}
              onChange={(e) => setForm({ ...form, market_value: e.target.value })}
              placeholder="0.00"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-gray-600 block mb-1.5">收益率 % (可选)</label>
            <input
              type="number"
              step="0.01"
              value={form.return_pct}
              onChange={(e) => setForm({ ...form, return_pct: e.target.value })}
              placeholder="0.00"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
          <p className="text-xs text-gray-400">基金名称、净值由系统自动获取</p>
        </div>
        <button
          onClick={() => void submit()}
          disabled={submitting}
          className="mt-6 w-full py-3 bg-gradient-to-r from-red-500 to-rose-500 text-white font-semibold rounded-xl hover:shadow-lg disabled:opacity-50"
        >
          {submitting ? "提交中..." : "确认添加"}
        </button>
      </div>
    </div>
  );
}
