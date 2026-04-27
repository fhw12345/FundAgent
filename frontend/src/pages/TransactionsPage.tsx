/**
 * Transactions page — 流水 / 定投 tabs.
 */

import { useState, useEffect, useCallback } from "react";
import {
  Plus,
  Trash2,
  RefreshCw,
  Calendar,
  X,
  ArrowUpRight,
  ArrowDownRight,
  ArrowLeftRight,
  Gift,
  Pause,
  Play,
} from "lucide-react";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

const headers = { "Content-Type": "application/json" };

interface Transaction {
  tx_id: string;
  fund_code: string;
  fund_name: string;
  tx_type: "buy" | "sell" | "convert" | "dividend_invest";
  date: string;
  submitted_at?: string | null;
  confirm_date?: string | null;
  status?: "pending" | "confirmed" | "failed";
  nav_source?: "estimated" | "confirmed";
  amount: number;
  shares: number;
  nav: number;
  fee: number;
  notes: string;
  is_dca: boolean;
}

interface DCAPlan {
  plan_id: string;
  fund_code: string;
  fund_name: string;
  frequency: "daily" | "weekly" | "biweekly" | "monthly";
  amount: number;
  day_of_month: number | null;
  day_of_week: number | null;
  anchor_date: string | null;
  status: "active" | "paused";
  last_executed: string | null;
  next_execution: string | null;
}

const TX_META = {
  buy: { label: "买入", color: "from-red-500 to-rose-500", bg: "bg-red-50", text: "text-red-600", Icon: ArrowUpRight },
  sell: { label: "卖出", color: "from-emerald-500 to-green-500", bg: "bg-emerald-50", text: "text-emerald-600", Icon: ArrowDownRight },
  convert: { label: "转换", color: "from-blue-500 to-indigo-500", bg: "bg-blue-50", text: "text-blue-600", Icon: ArrowLeftRight },
  dividend_invest: { label: "红利再投", color: "from-purple-500 to-pink-500", bg: "bg-purple-50", text: "text-purple-600", Icon: Gift },
} as const;

const FREQ_LABEL = {
  daily: "每日",
  weekly: "每周",
  biweekly: "每两周",
  monthly: "每月",
} as const;

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function TransactionsPage() {
  const [tab, setTab] = useState<"history" | "dca">("history");
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [plans, setPlans] = useState<DCAPlan[]>([]);
  const [filterType, setFilterType] = useState("");
  const [showTxModal, setShowTxModal] = useState(false);
  const [showDCAModal, setShowDCAModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterType) params.set("tx_type", filterType);
      const [txRes, planRes] = await Promise.all([
        fetch(`${API_BASE}/api/transactions?${params}`, { headers }),
        fetch(`${API_BASE}/api/dca-plans`, { headers }),
      ]);
      const txData = await txRes.json();
      const planData = await planRes.json();
      setTxs(txData.transactions || []);
      setPlans(planData.plans || []);
    } catch (e: unknown) {
      setError(`加载失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [filterType]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Group transactions by month
  const groupedTxs = (() => {
    const groups: Record<string, Transaction[]> = {};
    txs.forEach((tx) => {
      const d = new Date(tx.date);
      const key = `${d.getFullYear()}年${d.getMonth() + 1}月`;
      (groups[key] = groups[key] || []).push(tx);
    });
    return Object.entries(groups);
  })();

  const handleDeleteTx = async (tx_id: string) => {
    if (!confirm("确认删除该交易记录？")) return;
    await fetch(`${API_BASE}/api/transactions/${tx_id}`, { method: "DELETE", headers });
    void refresh();
  };

  const handleDeleteDCA = async (plan_id: string) => {
    if (!confirm("确认删除该定投计划？")) return;
    await fetch(`${API_BASE}/api/dca-plans/${plan_id}`, { method: "DELETE", headers });
    void refresh();
  };

  const handleToggleDCA = async (plan: DCAPlan) => {
    const action = plan.status === "active" ? "pause" : "resume";
    await fetch(`${API_BASE}/api/dca-plans/${plan.plan_id}/${action}`, { method: "PATCH", headers });
    void refresh();
  };

  return (
    <div className="max-w-3xl mx-auto pb-12">
      {/* Tab switcher */}
      <div className="sticky top-0 z-10 bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 px-4 pt-4 pb-2">
        <div className="flex bg-white rounded-2xl p-1 shadow-sm border border-gray-100">
          {(["history", "dca"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 text-sm font-semibold rounded-xl transition-all ${
                tab === t
                  ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md"
                  : "text-gray-600 hover:bg-gray-50"
              }`}
            >
              {t === "history" ? `交易流水 (${txs.length})` : `定投计划 (${plans.length})`}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-2 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)}><X className="w-4 h-4" /></button>
        </div>
      )}

      {tab === "history" && (
        <div className="px-4">
          {/* Pending T+1 banner */}
          {(() => {
            const pendingCount = txs.filter((t) => t.status === "pending").length;
            if (pendingCount === 0) return null;
            return (
              <div className="mt-3 bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200 rounded-xl px-4 py-3 flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center shrink-0">
                  <Calendar className="w-4 h-4 text-amber-600" />
                </div>
                <div className="flex-1 text-sm">
                  <div className="font-medium text-amber-900">{pendingCount} 笔交易待 T+1 确认</div>
                  <div className="text-xs text-amber-700 mt-0.5">
                    净值显示为估算值，明日 21 点后用真实净值更新
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Filter + add */}
          <div className="flex items-center justify-between gap-2 my-4">
            <div className="flex gap-1.5 overflow-x-auto">
              <FilterChip active={!filterType} onClick={() => setFilterType("")}>全部</FilterChip>
              {(["buy", "sell", "convert", "dividend_invest"] as const).map((t) => (
                <FilterChip key={t} active={filterType === t} onClick={() => setFilterType(t)}>
                  {TX_META[t].label}
                </FilterChip>
              ))}
            </div>
            <button
              onClick={() => void refresh()}
              disabled={loading}
              className="p-2 bg-white rounded-lg border border-gray-200 hover:bg-gray-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            <button
              onClick={() => setShowTxModal(true)}
              className="px-3.5 py-2 bg-gradient-to-r from-blue-500 to-indigo-500 text-white text-sm font-medium rounded-xl flex items-center gap-1 shadow-sm hover:shadow-md"
            >
              <Plus className="w-4 h-4" />
              添加
            </button>
          </div>

          {txs.length === 0 ? (
            <EmptyState text="暂无交易记录" hint="点击「添加」记录第一笔买入" />
          ) : (
            <div className="space-y-5">
              {groupedTxs.map(([month, items]) => (
                <div key={month}>
                  <div className="text-xs font-semibold text-gray-400 mb-2 px-1">{month}</div>
                  <div className="bg-white rounded-2xl shadow-sm border border-gray-100 divide-y divide-gray-50">
                    {items.map((tx) => (
                      <TxRow key={tx.tx_id} tx={tx} onDelete={() => void handleDeleteTx(tx.tx_id)} />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === "dca" && (
        <div className="px-4">
          <div className="flex items-center justify-end my-4">
            <button
              onClick={() => setShowDCAModal(true)}
              className="px-3.5 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white text-sm font-medium rounded-xl flex items-center gap-1 shadow-sm hover:shadow-md"
            >
              <Plus className="w-4 h-4" />
              新建定投
            </button>
          </div>
          {plans.length === 0 ? (
            <EmptyState text="还没有定投计划" hint="设置每日/每周/每两周/每月自动买入" />
          ) : (
            <div className="space-y-3">
              {plans.map((p) => (
                <DCACard
                  key={p.plan_id}
                  plan={p}
                  onToggle={() => void handleToggleDCA(p)}
                  onDelete={() => void handleDeleteDCA(p.plan_id)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {showTxModal && (
        <TransactionModal onClose={() => setShowTxModal(false)} onCreated={() => { setShowTxModal(false); void refresh(); }} />
      )}
      {showDCAModal && (
        <DCAModal onClose={() => setShowDCAModal(false)} onCreated={() => { setShowDCAModal(false); void refresh(); }} />
      )}
    </div>
  );
}

// ─── Atoms ───────────────────────────────────────────────────────────

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`px-3 py-1.5 text-xs font-medium rounded-full whitespace-nowrap transition-all ${
        active ? "bg-blue-500 text-white shadow-sm" : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

function EmptyState({ text, hint }: { text: string; hint: string }) {
  return (
    <div className="bg-white rounded-2xl p-12 text-center border border-gray-100 mt-4">
      <div className="w-16 h-16 mx-auto mb-3 bg-gray-50 rounded-2xl flex items-center justify-center">
        <Calendar className="w-8 h-8 text-gray-300" />
      </div>
      <p className="text-gray-500 font-medium">{text}</p>
      <p className="text-sm text-gray-400 mt-1">{hint}</p>
    </div>
  );
}

function TxRow({ tx, onDelete }: { tx: Transaction; onDelete: () => void }) {
  const meta = TX_META[tx.tx_type];
  const Icon = meta.Icon;
  const date = new Date(tx.date);
  const isPending = tx.status === "pending";
  const isFailed = tx.status === "failed";
  const isEstimated = tx.nav_source === "estimated" || isPending;
  return (
    <div className={`flex items-center gap-3 p-4 hover:bg-gray-50/50 ${isPending ? "bg-amber-50/30" : ""}`}>
      <div className={`w-10 h-10 rounded-full ${meta.bg} flex items-center justify-center shrink-0`}>
        <Icon className={`w-5 h-5 ${meta.text}`} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-medium text-gray-900 truncate">
            {meta.label} · {tx.fund_name || tx.fund_code}
          </span>
          {isPending && (
            <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded font-medium">
              待确认
            </span>
          )}
          {isFailed && (
            <span className="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded font-medium">
              确认失败
            </span>
          )}
          {tx.is_dca && <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-600 rounded">定投</span>}
        </div>
        <div className="text-xs text-gray-400 mt-0.5">
          {date.getMonth() + 1}/{date.getDate()} · 净值 {tx.nav.toFixed(4)}
          {isEstimated && <span className="text-amber-600 ml-0.5">(估算)</span>}
          {" · "}{Math.abs(tx.shares).toFixed(2)} 份
          {tx.fee > 0 && ` · 费 ${tx.fee.toFixed(2)}`}
        </div>
        {isPending && tx.confirm_date && (
          <div className="text-[11px] text-amber-600 mt-1">
            预计 {new Date(tx.confirm_date).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })} 确认实际净值
          </div>
        )}
      </div>
      <div className="text-right">
        <div className={`font-bold ${meta.text}`}>
          {tx.tx_type === "sell" ? "+" : "-"}¥{tx.amount.toFixed(2)}
        </div>
      </div>
      <button onClick={onDelete} className="p-1.5 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg">
        <Trash2 className="w-4 h-4" />
      </button>
    </div>
  );
}

function DCACard({ plan, onToggle, onDelete }: { plan: DCAPlan; onToggle: () => void; onDelete: () => void }) {
  const isActive = plan.status === "active";
  const freqLabel = FREQ_LABEL[plan.frequency];
  let detail = "";
  if (plan.frequency === "monthly" && plan.day_of_month) detail = `每月 ${plan.day_of_month} 日`;
  else if (plan.frequency === "weekly" && plan.day_of_week) detail = `每${WEEKDAYS[plan.day_of_week - 1]}`;
  else if (plan.frequency === "biweekly" && plan.anchor_date) detail = `每两周 (起始 ${new Date(plan.anchor_date).toLocaleDateString("zh-CN")})`;
  else if (plan.frequency === "daily") detail = "每日";

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${
              isActive ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"
            }`}>
              {isActive ? "● 执行中" : "○ 已暂停"}
            </span>
            <span className="text-xs text-gray-500 font-mono">{plan.fund_code}</span>
          </div>
          <h4 className="font-semibold text-gray-900 truncate">{plan.fund_name || "未知基金"}</h4>
        </div>
        <div className="flex gap-1">
          <button
            onClick={onToggle}
            className="p-2 text-gray-400 hover:text-blue-500 hover:bg-blue-50 rounded-lg"
            title={isActive ? "暂停" : "恢复"}
          >
            {isActive ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </button>
          <button
            onClick={onDelete}
            className="p-2 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-lg"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <div className="text-xs text-gray-400 mb-0.5">频率</div>
          <div className="font-medium">{freqLabel}</div>
        </div>
        <div>
          <div className="text-xs text-gray-400 mb-0.5">每次金额</div>
          <div className="font-bold text-purple-600">¥{plan.amount}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-gray-400 mb-0.5">下次执行</div>
          <div className="font-medium text-gray-700">
            {plan.next_execution ? new Date(plan.next_execution).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" }) : "-"}
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-gray-50 text-xs text-gray-500">
        {detail}
        {plan.last_executed && ` · 上次 ${new Date(plan.last_executed).toLocaleDateString("zh-CN")}`}
      </div>
    </div>
  );
}

// ─── Modals ──────────────────────────────────────────────────────────

function TransactionModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    fund_code: "",
    tx_type: "buy" as Transaction["tx_type"],
    date: new Date().toISOString().slice(0, 10),
    amount: "",
    nav: "",
    fee: "",
    source_fund_code: "",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!form.fund_code.match(/^\d{6}$/)) return setErr("基金代码须为6位数字");
    if (!form.amount || parseFloat(form.amount) <= 0) return setErr("请输入有效金额");
    setSubmitting(true);
    setErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/transactions`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          fund_code: form.fund_code,
          tx_type: form.tx_type,
          date: new Date(form.date).toISOString(),
          amount: parseFloat(form.amount),
          nav: form.nav ? parseFloat(form.nav) : null,
          fee: form.fee ? parseFloat(form.fee) : 0,
          source_fund_code: form.tx_type === "convert" ? form.source_fund_code : null,
          notes: form.notes,
        }),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || `HTTP ${res.status}`);
      }
      onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="添加交易" onClose={onClose}>
      {err && <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-lg mb-4">{err}</div>}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-2">交易类型</label>
          <div className="grid grid-cols-4 gap-2">
            {(Object.keys(TX_META) as Transaction["tx_type"][]).map((t) => {
              const m = TX_META[t];
              const Icon = m.Icon;
              const active = form.tx_type === t;
              return (
                <button
                  key={t}
                  onClick={() => setForm({ ...form, tx_type: t })}
                  className={`flex flex-col items-center gap-1 py-3 rounded-xl text-xs transition-all ${
                    active
                      ? `bg-gradient-to-br ${m.color} text-white shadow-md`
                      : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="font-medium">{m.label}</span>
                </button>
              );
            })}
          </div>
        </div>
        <Field label="基金代码">
          <input
            type="text"
            value={form.fund_code}
            onChange={(e) => setForm({ ...form, fund_code: e.target.value })}
            maxLength={6}
            placeholder="110011"
            className="modal-input"
          />
        </Field>
        {form.tx_type === "convert" && (
          <Field label="转换源基金代码">
            <input
              type="text"
              value={form.source_fund_code}
              onChange={(e) => setForm({ ...form, source_fund_code: e.target.value })}
              maxLength={6}
              className="modal-input"
            />
          </Field>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Field label="日期">
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} className="modal-input" />
          </Field>
          <Field label="金额 (元)">
            <input type="number" step="0.01" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="modal-input" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="净值 (留空自动获取)">
            <input type="number" step="0.0001" value={form.nav} onChange={(e) => setForm({ ...form, nav: e.target.value })} className="modal-input" />
          </Field>
          <Field label="手续费">
            <input type="number" step="0.01" value={form.fee} onChange={(e) => setForm({ ...form, fee: e.target.value })} className="modal-input" placeholder="0" />
          </Field>
        </div>
        <Field label="备注 (可选)">
          <input type="text" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} className="modal-input" />
        </Field>
      </div>
      <div className="mt-4 bg-amber-50 border border-amber-100 rounded-xl p-3 text-xs text-amber-700 leading-relaxed">
        💡 真实下单遵循 T+1 规则：15:00 前下单按当日净值，之后顺延一个交易日。提交后状态显示为「待确认」，次个交易日 21 点后系统自动用实际净值确认份额。
      </div>
      <button
        onClick={() => void submit()}
        disabled={submitting}
        className="mt-6 w-full py-3 bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold rounded-xl hover:shadow-lg disabled:opacity-50"
      >
        {submitting ? "提交中..." : "确认添加"}
      </button>
    </ModalShell>
  );
}

function DCAModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({
    fund_code: "",
    frequency: "monthly" as DCAPlan["frequency"],
    amount: "",
    day_of_month: "15",
    day_of_week: "1",
    anchor_date: new Date().toISOString().slice(0, 10),
  });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!form.fund_code.match(/^\d{6}$/)) return setErr("基金代码须为6位数字");
    if (!form.amount || parseFloat(form.amount) <= 0) return setErr("请输入有效金额");
    setSubmitting(true);
    setErr(null);
    try {
      const body: Record<string, unknown> = {
        fund_code: form.fund_code,
        frequency: form.frequency,
        amount: parseFloat(form.amount),
      };
      if (form.frequency === "monthly") body.day_of_month = parseInt(form.day_of_month, 10);
      if (form.frequency === "weekly" || form.frequency === "biweekly") body.day_of_week = parseInt(form.day_of_week, 10);
      if (form.frequency === "biweekly") body.anchor_date = new Date(form.anchor_date).toISOString();

      const res = await fetch(`${API_BASE}/api/dca-plans`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || `HTTP ${res.status}`);
      }
      onCreated();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ModalShell title="新建定投计划" onClose={onClose}>
      {err && <div className="bg-red-50 text-red-700 text-sm px-3 py-2 rounded-lg mb-4">{err}</div>}
      <div className="space-y-4">
        <div>
          <label className="text-xs font-medium text-gray-600 block mb-2">定投周期</label>
          <div className="grid grid-cols-4 gap-2">
            {(Object.keys(FREQ_LABEL) as DCAPlan["frequency"][]).map((f) => (
              <button
                key={f}
                onClick={() => setForm({ ...form, frequency: f })}
                className={`py-2.5 rounded-xl text-sm font-medium transition-all ${
                  form.frequency === f
                    ? "bg-gradient-to-br from-purple-500 to-pink-500 text-white shadow-md"
                    : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                }`}
              >
                {FREQ_LABEL[f]}
              </button>
            ))}
          </div>
        </div>

        <Field label="基金代码">
          <input
            type="text"
            value={form.fund_code}
            onChange={(e) => setForm({ ...form, fund_code: e.target.value })}
            maxLength={6}
            placeholder="110011"
            className="modal-input"
          />
        </Field>

        <Field label="每次金额 (元)">
          <input
            type="number"
            step="0.01"
            value={form.amount}
            onChange={(e) => setForm({ ...form, amount: e.target.value })}
            placeholder="500"
            className="modal-input"
          />
        </Field>

        {form.frequency === "monthly" && (
          <Field label="每月扣款日 (1-28)">
            <input
              type="number"
              min="1"
              max="28"
              value={form.day_of_month}
              onChange={(e) => setForm({ ...form, day_of_month: e.target.value })}
              className="modal-input"
            />
          </Field>
        )}

        {(form.frequency === "weekly" || form.frequency === "biweekly") && (
          <Field label="每周扣款日">
            <div className="grid grid-cols-7 gap-1.5">
              {WEEKDAYS.map((label, i) => (
                <button
                  key={i}
                  onClick={() => setForm({ ...form, day_of_week: String(i + 1) })}
                  className={`py-2 text-xs rounded-lg font-medium ${
                    parseInt(form.day_of_week, 10) === i + 1
                      ? "bg-purple-500 text-white"
                      : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {label.replace("周", "")}
                </button>
              ))}
            </div>
          </Field>
        )}

        {form.frequency === "biweekly" && (
          <Field label="起始日期 (用于计算双周间隔)">
            <input
              type="date"
              value={form.anchor_date}
              onChange={(e) => setForm({ ...form, anchor_date: e.target.value })}
              className="modal-input"
            />
          </Field>
        )}

        <div className="bg-purple-50 border border-purple-100 rounded-xl p-3 text-xs text-purple-700">
          {form.frequency === "daily" && "💡 每日按当日净值买入，工作日和周末都执行"}
          {form.frequency === "weekly" && `💡 每${WEEKDAYS[parseInt(form.day_of_week, 10) - 1]}按当日净值买入`}
          {form.frequency === "biweekly" && `💡 从起始日起，每隔14天执行一次`}
          {form.frequency === "monthly" && `💡 每月 ${form.day_of_month} 日按当日净值买入；当月只执行一次`}
        </div>
      </div>

      <button
        onClick={() => void submit()}
        disabled={submitting}
        className="mt-6 w-full py-3 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-xl hover:shadow-lg disabled:opacity-50"
      >
        {submitting ? "创建中..." : "创建定投计划"}
      </button>
    </ModalShell>
  );
}

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 p-0 sm:p-4">
      <div className="bg-white rounded-t-3xl sm:rounded-3xl shadow-xl w-full sm:max-w-md p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>
        {children}
      </div>
      <style>{`.modal-input { width: 100%; padding: 0.75rem 1rem; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 0.75rem; font-size: 1rem; outline: none; transition: all 0.15s; }
      .modal-input:focus { background: white; box-shadow: 0 0 0 2px #3b82f6; border-color: transparent; }`}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-600 block mb-1.5">{label}</label>
      {children}
    </div>
  );
}
