/**
 * Portfolio Dashboard — Fund holdings management with screenshot import.
 */

import { useState, useCallback, useRef } from "react";
import { Upload, Camera, Trash2, RefreshCw, Plus, TrendingUp } from "lucide-react";
import { authStorage } from "../services/authService";

interface Holding {
  fund_code: string;
  fund_name: string;
  shares: number | null;
  nav: number | null;
  market_value: number | null;
  return_pct: number | null;
}

interface Portfolio {
  holdings: Holding[];
  source: string | null;
  updated_at: string | null;
}

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

function authHeaders() {
  const token = authStorage.getToken();
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export default function PortfolioDashboard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [manualCode, setManualCode] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchPortfolio = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio`, { headers: authHeaders() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPortfolio(data);
    } catch (e: unknown) {
      setError(`加载持仓失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load on first render
  useState(() => { void fetchPortfolio(); });

  const handleScreenshotUpload = async (file: File) => {
    setImporting(true);
    setError(null);
    try {
      const reader = new FileReader();
      const base64 = await new Promise<string>((resolve, reject) => {
        reader.onload = () => {
          const result = reader.result as string;
          resolve(result.split(",")[1]);
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });

      const res = await fetch(`${API_BASE}/api/portfolio/import-screenshot`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ image_base64: base64 }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setPortfolio(data.portfolio);
      setAnalysisResult(`成功导入 ${data.imported_count} 只基金`);
    } catch (e: unknown) {
      setError(`截图导入失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setImporting(false);
    }
  };

  const handleAddManual = async () => {
    if (!manualCode.match(/^\d{6}$/)) {
      setError("请输入6位基金代码");
      return;
    }
    const existing = portfolio?.holdings || [];
    if (existing.some((h) => h.fund_code === manualCode)) {
      setError("该基金已在持仓中");
      return;
    }
    const newHoldings = [...existing, { fund_code: manualCode, fund_name: "", shares: null, nav: null, market_value: null, return_pct: null }];
    try {
      const res = await fetch(`${API_BASE}/api/portfolio`, {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ holdings: newHoldings }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPortfolio(data);
      setManualCode("");
      setError(null);
    } catch (e: unknown) {
      setError(`添加失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleRemove = async (code: string) => {
    const newHoldings = (portfolio?.holdings || []).filter((h) => h.fund_code !== code);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio`, {
        method: "PUT",
        headers: authHeaders(),
        body: JSON.stringify({ holdings: newHoldings }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPortfolio(data);
    } catch (e: unknown) {
      setError(`删除失败: ${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const handleDailyAnalysis = async () => {
    setAnalyzing(true);
    setAnalysisResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/portfolio/daily-analysis`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setAnalysisResult(`已启动分析 ${data.fund_count} 只基金，请稍后在对话中查看结果`);
    } catch (e: unknown) {
      setError(`分析启动失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const holdings = portfolio?.holdings || [];

  return (
    <div className="max-w-4xl mx-auto p-4 sm:p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">我的基金持仓</h2>
        <div className="flex gap-2">
          <button
            onClick={() => void fetchPortfolio()}
            disabled={loading}
            className="px-3 py-2 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg flex items-center gap-1 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </button>
          <button
            onClick={() => void handleDailyAnalysis()}
            disabled={analyzing || holdings.length === 0}
            className="px-4 py-2 text-sm bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg flex items-center gap-1 hover:shadow-lg transition-all disabled:opacity-50"
          >
            <TrendingUp className="w-4 h-4" />
            {analyzing ? "分析中..." : "一键分析"}
          </button>
        </div>
      </div>

      {/* Error / Success messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {error}
        </div>
      )}
      {analysisResult && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg text-sm">
          {analysisResult}
        </div>
      )}

      {/* Import section */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">导入持仓</h3>
        <div className="flex flex-col sm:flex-row gap-4">
          {/* Screenshot upload */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="flex-1 border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition-all"
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleScreenshotUpload(file);
              }}
            />
            {importing ? (
              <div className="flex flex-col items-center gap-2">
                <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
                <span className="text-sm text-gray-600">AI 识别中...</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Camera className="w-8 h-8 text-gray-400" />
                <span className="text-sm text-gray-600">上传持仓截图</span>
                <span className="text-xs text-gray-400">支持支付宝/天天基金/蛋卷截图</span>
              </div>
            )}
          </div>

          {/* Manual add */}
          <div className="flex-1 flex flex-col gap-3">
            <div className="flex gap-2">
              <input
                type="text"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                placeholder="输入基金代码 (如 110011)"
                maxLength={6}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => void handleAddManual()}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600 flex items-center gap-1"
              >
                <Plus className="w-4 h-4" />
                添加
              </button>
            </div>
            <p className="text-xs text-gray-400">手动添加基金代码到持仓列表</p>
          </div>
        </div>
      </div>

      {/* Holdings table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-800">
            持仓列表
            <span className="ml-2 text-sm font-normal text-gray-500">
              ({holdings.length} 只基金)
            </span>
          </h3>
          {portfolio?.source && (
            <span className="text-xs text-gray-400">
              来源: {portfolio.source === "screenshot" ? "截图导入" : "手动添加"}
              {portfolio.updated_at && ` · ${new Date(portfolio.updated_at).toLocaleString("zh-CN")}`}
            </span>
          )}
        </div>

        {holdings.length === 0 ? (
          <div className="p-12 text-center text-gray-400">
            <Upload className="w-12 h-12 mx-auto mb-3 opacity-50" />
            <p className="text-lg font-medium">暂无持仓</p>
            <p className="text-sm mt-1">上传截图或手动添加基金代码</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">基金代码</th>
                  <th className="px-4 py-3 text-left font-medium">基金名称</th>
                  <th className="px-4 py-3 text-right font-medium">持有份额</th>
                  <th className="px-4 py-3 text-right font-medium">最新净值</th>
                  <th className="px-4 py-3 text-right font-medium">持仓市值</th>
                  <th className="px-4 py-3 text-right font-medium">收益率</th>
                  <th className="px-4 py-3 text-center font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {holdings.map((h) => (
                  <tr key={h.fund_code} className="hover:bg-gray-50/50">
                    <td className="px-4 py-3 font-mono text-blue-600">{h.fund_code}</td>
                    <td className="px-4 py-3">{h.fund_name || "-"}</td>
                    <td className="px-4 py-3 text-right">{h.shares?.toFixed(2) ?? "-"}</td>
                    <td className="px-4 py-3 text-right">{h.nav?.toFixed(4) ?? "-"}</td>
                    <td className="px-4 py-3 text-right">{h.market_value?.toFixed(2) ?? "-"}</td>
                    <td className={`px-4 py-3 text-right font-medium ${
                      h.return_pct != null
                        ? h.return_pct >= 0
                          ? "text-red-600"
                          : "text-green-600"
                        : ""
                    }`}>
                      {h.return_pct != null ? `${h.return_pct >= 0 ? "+" : ""}${h.return_pct.toFixed(2)}%` : "-"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <button
                        onClick={() => void handleRemove(h.fund_code)}
                        className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                        title="移除"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
