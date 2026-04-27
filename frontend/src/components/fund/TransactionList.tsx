import { useEffect, useState } from "react";

const API_BASE =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.MODE === "production"
      ? ""
      : "http://localhost:8000";

interface Transaction {
  _id?: string;
  fund_code: string;
  tx_type: string;
  date: string;
  amount: number;
  shares: number;
  nav?: number;
  status: string;
}

const TYPE_LABEL: Record<string, string> = {
  buy: "申购",
  sell: "赎回",
  convert: "转换",
  dividend_invest: "分红再投",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "待确认",
  confirmed: "已确认",
};

interface Props {
  fundCode: string;
}

export default function TransactionList({ fundCode }: Props) {
  const [txs, setTxs] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(
      `${API_BASE}/api/transactions?fund_code=${encodeURIComponent(fundCode)}&limit=50`,
      { headers: { "Content-Type": "application/json" } },
    )
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((d) => {
        if (cancelled) return;
        const list: Transaction[] = d.transactions || [];
        list.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
        setTxs(list);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [fundCode]);

  if (loading) {
    return <div className="text-sm text-gray-400 py-6 text-center">加载中...</div>;
  }
  if (error) {
    return (
      <div className="text-sm text-red-600 py-4 px-3 bg-red-50 rounded-lg">
        加载失败: {error}
      </div>
    );
  }
  if (txs.length === 0) {
    return <div className="text-sm text-gray-400 py-6 text-center">暂无交易记录</div>;
  }

  return (
    <div className="divide-y divide-gray-50">
      {txs.map((t) => {
        const typeLabel = TYPE_LABEL[t.tx_type] ?? t.tx_type;
        const isOut = t.tx_type === "sell";
        return (
          <div
            key={t._id ?? `${t.date}-${t.amount}`}
            className="flex items-center justify-between px-1 py-3 text-sm"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${
                    isOut ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                  }`}
                >
                  {typeLabel}
                </span>
                <span className="text-gray-500 text-xs">
                  {String(t.date).slice(0, 10)}
                </span>
                {t.status === "pending" && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded">
                    {STATUS_LABEL[t.status] ?? t.status}
                  </span>
                )}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                {Math.abs(t.shares).toFixed(2)} 份 · 净值 {t.nav?.toFixed(4) ?? "-"}
              </div>
            </div>
            <div
              className={`font-semibold tabular-nums ${
                isOut ? "text-emerald-600" : "text-red-600"
              }`}
            >
              {isOut ? "-" : "+"}¥{t.amount.toFixed(2)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
