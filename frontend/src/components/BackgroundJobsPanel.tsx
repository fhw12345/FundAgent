/**
 * Background Jobs Panel — shows recent runs of async background tasks
 * (DCA scheduler, T+1 NAV confirmation, etc.) persisted to MongoDB.
 */

import { useState, useEffect } from "react";
import { RefreshCw, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

interface JobRun {
  run_id: string;
  job_name: string;
  started_at: string;
  finished_at: string | null;
  status: "running" | "ok" | "error";
  items_processed: number;
  error: string | null;
}

const JOB_LABELS: Record<string, string> = {
  dca_scheduler: "定投调度器",
  tplus1_confirmation: "T+1 净值确认",
};

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", { hour12: false });
}

function durationMs(start: string, end: string | null): string {
  if (!end) return "—";
  const ms = new Date(end).getTime() - new Date(start).getTime();
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export default function BackgroundJobsPanel() {
  const [summary, setSummary] = useState<JobRun[]>([]);
  const [recent, setRecent] = useState<JobRun[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, r] = await Promise.all([
        fetch(`${API_BASE}/api/jobs/summary`).then((x) => x.json() as Promise<{ jobs: JobRun[] }>),
        fetch(`${API_BASE}/api/jobs/recent?limit=20`).then((x) => x.json() as Promise<{ runs: JobRun[] }>),
      ]);
      setSummary(s.jobs || []);
      setRecent(r.runs || []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchAll();
    const t = setInterval(() => void fetchAll(), 30000);
    return () => clearInterval(t);
  }, []);

  const statusBadge = (status: JobRun["status"]) => {
    if (status === "ok")
      return (
        <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded text-xs font-medium">
          <CheckCircle2 className="w-3 h-3" /> 成功
        </span>
      );
    if (status === "error")
      return (
        <span className="inline-flex items-center gap-1 text-red-700 bg-red-50 px-2 py-0.5 rounded text-xs font-medium">
          <AlertCircle className="w-3 h-3" /> 失败
        </span>
      );
    return (
      <span className="inline-flex items-center gap-1 text-blue-700 bg-blue-50 px-2 py-0.5 rounded text-xs font-medium">
        <Loader2 className="w-3 h-3 animate-spin" /> 运行中
      </span>
    );
  };

  return (
    <div className="bg-white rounded-lg shadow mb-6 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900">后台任务</h2>
        <button
          onClick={() => void fetchAll()}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50 rounded-lg border border-gray-200"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          刷新
        </button>
      </div>

      {error && (
        <div className="px-6 py-3 bg-red-50 text-red-700 text-sm">加载失败: {error}</div>
      )}

      {/* Summary cards (latest run per job) */}
      <div className="px-6 py-4 grid grid-cols-1 md:grid-cols-2 gap-3 border-b border-gray-100">
        {summary.length === 0 && !loading && (
          <div className="text-sm text-gray-500 col-span-full">暂无任务执行记录</div>
        )}
        {summary.map((j) => (
          <div
            key={j.job_name}
            className="border border-gray-200 rounded-lg p-3 flex items-start justify-between"
          >
            <div className="min-w-0">
              <div className="font-medium text-gray-900 text-sm">
                {JOB_LABELS[j.job_name] ?? j.job_name}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                最近: {formatTime(j.started_at)}
              </div>
              <div className="text-xs text-gray-500">
                耗时 {durationMs(j.started_at, j.finished_at)} · 处理 {j.items_processed} 项
              </div>
              {j.error && (
                <div className="text-xs text-red-600 mt-1 truncate" title={j.error}>
                  {j.error}
                </div>
              )}
            </div>
            <div className="ml-3 shrink-0">{statusBadge(j.status)}</div>
          </div>
        ))}
      </div>

      {/* Recent history */}
      <div>
        <div className="px-6 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider bg-gray-50">
          最近执行
        </div>
        <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
          {recent.map((r) => (
            <div key={r.run_id} className="px-6 py-2.5 flex items-center text-sm hover:bg-gray-50">
              <div className="w-32 shrink-0 text-gray-700 font-medium">
                {JOB_LABELS[r.job_name] ?? r.job_name}
              </div>
              <div className="flex-1 text-gray-500 font-mono text-xs">
                {formatTime(r.started_at)}
              </div>
              <div className="w-20 text-right text-xs text-gray-500">
                {durationMs(r.started_at, r.finished_at)}
              </div>
              <div className="w-16 text-right text-xs text-gray-500">{r.items_processed}</div>
              <div className="w-24 text-right">{statusBadge(r.status)}</div>
            </div>
          ))}
          {recent.length === 0 && !loading && (
            <div className="px-6 py-4 text-sm text-gray-400 text-center">无记录</div>
          )}
        </div>
      </div>
    </div>
  );
}
