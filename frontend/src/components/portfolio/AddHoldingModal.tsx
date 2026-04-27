import { useState } from "react";
import { X } from "lucide-react";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

const headers = { "Content-Type": "application/json" };

interface Props {
  onClose: () => void;
  onAdded: () => void;
}

export default function AddHoldingModal({ onClose, onAdded }: Props) {
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
            <label htmlFor="ah-fund-code" className="text-xs font-medium text-gray-600 block mb-1.5">基金代码</label>
            <input
              id="ah-fund-code"
              type="text"
              value={form.fund_code}
              onChange={(e) => setForm({ ...form, fund_code: e.target.value })}
              maxLength={6}
              placeholder="如 110011"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
          <div>
            <label htmlFor="ah-market-value" className="text-xs font-medium text-gray-600 block mb-1.5">持仓金额 (元)</label>
            <input
              id="ah-market-value"
              type="number"
              step="0.01"
              value={form.market_value}
              onChange={(e) => setForm({ ...form, market_value: e.target.value })}
              placeholder="0.00"
              className="w-full px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white"
            />
          </div>
          <div>
            <label htmlFor="ah-return-pct" className="text-xs font-medium text-gray-600 block mb-1.5">收益率 % (可选)</label>
            <input
              id="ah-return-pct"
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
