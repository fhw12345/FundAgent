# Portfolio Dashboard & Fund Detail Page Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Match the two reference screenshots — restyle holding cards, make hero P&L collapsible, add tabs to the fund detail page with personal holding view (summary + transaction history) and a NAV chart with week/month/year toggle.

**Architecture:** Mostly frontend. Split `PortfolioDashboard.tsx` and `FundDetailPage.tsx` into focused subcomponents under `frontend/src/components/portfolio/` and `frontend/src/components/fund/`. Backend change is a single one-line tweak: `tail(90)` → `tail(250)` in `fund_detail.py` so the NAV chart can slice client-side. `/api/transactions` already supports `fund_code` filter, so no new endpoint is needed.

**Tech Stack:** React 18 + TypeScript + Vite + TailwindCSS (frontend); FastAPI + AkShare (backend).

**Spec:** `docs/superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md`

---

## File Map

### Backend
- Modify: `backend/src/api/fund_detail.py:51` — change `tail(90)` to `tail(250)`.

### Frontend (new)
- Create: `frontend/src/components/portfolio/HeroCard.tsx` — hero card with collapsible P&L breakdown.
- Create: `frontend/src/components/portfolio/FundCard.tsx` — restyled holding card.
- Create: `frontend/src/components/portfolio/AddHoldingModal.tsx` — extracted modal.
- Create: `frontend/src/components/fund/NavChart.tsx` — chart with week/month/year toggle.
- Create: `frontend/src/components/fund/TransactionList.tsx` — per-fund transaction list.
- Create: `frontend/src/components/fund/MyHoldingTab.tsx` — holding summary + chart + transactions.
- Create: `frontend/src/components/fund/FundInfoTab.tsx` — chart + top holdings + basic info.

### Frontend (modify)
- Modify: `frontend/src/pages/PortfolioDashboard.tsx` — slim down: extract HeroCard, FundCard, AddHoldingModal.
- Modify: `frontend/src/pages/FundDetailPage.tsx` — wrap content in tabs; delegate to MyHoldingTab/FundInfoTab.

---

## Conventions (apply to every task)

- **Branch:** create once at the start (`users/haowen/portfolio-fund-redesign`) and commit on it for every task.
- **Commit message format:** `feat(scope): message` or `refactor(scope): message`. Append the standard `Co-Authored-By: Claude ...` trailer per CLAUDE.md.
- **Pre-commit:** project enforces version bump on every commit (see CLAUDE.md). Run `./scripts/bump-version.sh frontend patch` before each frontend-touching commit; `backend patch` before backend-touching commit. The single-task version bump is intentional — many small bumps are fine.
- **Lint/format:** `docker compose exec frontend npm run lint` for frontend; `cd backend && make lint` for backend.
- **No new tests required** unless a Task explicitly defines one. CLAUDE.md prefers verifying via local docker-compose + browser; testing strategy is covered in the spec's Testing section.
- **All file paths in this plan are relative to repo root** `C:\Users\haowenfeng\repo\FinancialAgent\`.

---

## Task 0: Branch & Setup

**Files:** none (git only)

- [ ] **Step 1: Create feature branch from main**

```bash
git checkout main
git pull --ff-only
git checkout -b users/haowen/portfolio-fund-redesign
```

- [ ] **Step 2: Verify dev stack runs**

```bash
make dev
curl http://localhost:8000/api/health
```

Expected: backend returns 200; frontend reachable at http://localhost:3000.

---

## Task 1: Backend — extend NAV history to 1 year

**Files:**
- Modify: `backend/src/api/fund_detail.py:51`

- [ ] **Step 1: Change NAV tail length**

In `backend/src/api/fund_detail.py`, find:

```python
            tail = df.tail(90)
```

Replace with:

```python
            tail = df.tail(250)
```

- [ ] **Step 2: Verify locally**

```bash
docker compose restart backend
curl -s -o /tmp/fd.json -w "%{http_code}\n" \
  -H "Cookie: <auth-cookie>" \
  http://localhost:8000/api/funds/110011
python -c "import json; d=json.load(open('/tmp/fd.json')); print(len(d['nav_history']))"
```

Expected: HTTP 200, length around 250 (may be less if AkShare returns fewer points).

> If you cannot easily get an auth cookie, skip the curl check — it will be exercised end-to-end in Task 11.

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh backend patch
git add backend/src/api/fund_detail.py backend/src/version.py docs/project/versions/backend/CHANGELOG.md
git commit -m "feat(funds): return 1yr of NAV history for client-side range switching"
```

(Path to `version.py` / CHANGELOG may differ — let `bump-version.sh` print the file paths and stage what it touched.)

---

## Task 2: Frontend — extract `AddHoldingModal`

**Files:**
- Create: `frontend/src/components/portfolio/AddHoldingModal.tsx`
- Modify: `frontend/src/pages/PortfolioDashboard.tsx`

- [ ] **Step 1: Create the new file**

Create `frontend/src/components/portfolio/AddHoldingModal.tsx` with the contents of the existing `AddHoldingModal` component currently inside `PortfolioDashboard.tsx` (lines ~481–581 in the current file). Add the imports it needs at the top:

```tsx
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
  // ... existing modal body verbatim ...
}
```

Copy the full modal body verbatim from the current `PortfolioDashboard.tsx`.

- [ ] **Step 2: Update `PortfolioDashboard.tsx`**

Remove the inline `AddHoldingModal` function (and its props interface). Add an import:

```tsx
import AddHoldingModal from "../components/portfolio/AddHoldingModal";
```

Leave the `<AddHoldingModal ... />` JSX usage unchanged.

- [ ] **Step 3: Verify build**

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 4: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/portfolio/AddHoldingModal.tsx \
        frontend/src/pages/PortfolioDashboard.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "refactor(portfolio): extract AddHoldingModal into its own file"
```

---

## Task 3: Frontend — create `HeroCard` with collapsible P&L

**Files:**
- Create: `frontend/src/components/portfolio/HeroCard.tsx`
- Modify: `frontend/src/pages/PortfolioDashboard.tsx`

- [ ] **Step 1: Create `HeroCard.tsx`**

```tsx
import { useState } from "react";
import { RefreshCw, ChevronDown } from "lucide-react";

interface Props {
  totalAssets: number;
  todayTotalEstPnl: number | null;
  totalUnrealized: number;
  totalRealized: number;
  totalReturnPct: number;
  loading: boolean;
  onRefresh: () => void;
}

export default function HeroCard({
  totalAssets,
  todayTotalEstPnl,
  totalUnrealized,
  totalRealized,
  totalReturnPct,
  loading,
  onRefresh,
}: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="relative overflow-hidden bg-gradient-to-br from-red-500 via-rose-500 to-red-600 text-white p-6 sm:p-8 sm:rounded-3xl sm:mt-4 mx-0 sm:mx-4 shadow-xl shadow-red-500/30">
      <div className="absolute -right-12 -top-12 w-48 h-48 bg-white/10 rounded-full" />
      <div className="absolute -right-4 -bottom-16 w-40 h-40 bg-white/5 rounded-full" />
      <div className="relative">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm text-white/80">基金总资产 (元)</span>
          <button
            onClick={onRefresh}
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

        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm">
            <span className="text-white/70 text-xs mr-2">持有收益率</span>
            <span className="font-semibold">
              {totalReturnPct >= 0 ? "+" : ""}
              {totalReturnPct.toFixed(2)}%
            </span>
          </div>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 text-xs text-white/80 hover:text-white"
          >
            {expanded ? "收起明细" : "展开明细"}
            <ChevronDown
              className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-180" : ""}`}
            />
          </button>
        </div>

        {expanded && (
          <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/20 text-sm">
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
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Use `HeroCard` in `PortfolioDashboard.tsx`**

At the top of `PortfolioDashboard.tsx` add the import:

```tsx
import HeroCard from "../components/portfolio/HeroCard";
```

Replace the entire `<div className="relative overflow-hidden bg-gradient-to-br ...">` hero block (currently the first child of the `max-w-3xl` wrapper, ~lines 191–240) with:

```tsx
<HeroCard
  totalAssets={totalAssets}
  todayTotalEstPnl={todayTotalEstPnl}
  totalUnrealized={totalUnrealized}
  totalRealized={totalRealized}
  totalReturnPct={totalReturnPct}
  loading={loading}
  onRefresh={() => void refresh()}
/>
```

Remove now-unused `RefreshCw` from the page-level lucide import if no other code uses it. Keep all other imports.

- [ ] **Step 3: Verify**

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

Open `http://localhost:3000`, log in, confirm the hero card shows total assets + today's estimate + 持有收益率 + 「展开明细」 button. Click button — three-column block toggles.

- [ ] **Step 4: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/portfolio/HeroCard.tsx \
        frontend/src/pages/PortfolioDashboard.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(portfolio): collapsible hero P&L breakdown via HeroCard"
```

---

## Task 4: Frontend — restyle `FundCard`

**Files:**
- Create: `frontend/src/components/portfolio/FundCard.tsx`
- Modify: `frontend/src/pages/PortfolioDashboard.tsx`

- [ ] **Step 1: Create `FundCard.tsx`**

```tsx
import {
  TrendingUp,
  TrendingDown,
  ChevronRight,
  ShoppingCart,
} from "lucide-react";

export interface FundCardHolding {
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
}

interface Props {
  holding: FundCardHolding;
}

export default function FundCard({ holding }: Props) {
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
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-500">{holding.fund_code}</span>
            {holding.has_tx && (
              <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded">
                已建仓
              </span>
            )}
          </div>
          <h4 className="font-semibold text-gray-900 truncate">
            {holding.fund_name || "未知基金"}
          </h4>
        </div>
        <ChevronRight className="w-5 h-5 text-gray-300 group-hover:text-gray-500 group-hover:translate-x-0.5 transition-all" />
      </div>

      {/* Data row: today estimate (left, big) | return % (middle) | market value (right, small) */}
      <div className="grid grid-cols-3 gap-3 items-end">
        <div>
          <div className="text-[11px] text-gray-400 mb-0.5">当日估算</div>
          {todayPct != null ? (
            <div>
              <div className={`text-xl font-bold leading-tight ${todayColor}`}>
                {todayUp ? "+" : ""}
                {todayPct.toFixed(2)}%
              </div>
              {todayPnl != null && (
                <div className={`text-[11px] font-medium mt-0.5 ${todayColor}`}>
                  {todayUp ? "+" : ""}
                  ¥{todayPnl.toFixed(2)}
                </div>
              )}
            </div>
          ) : (
            <div className="text-gray-400 text-sm">暂无</div>
          )}
        </div>

        <div className="text-center">
          <div className="text-[11px] text-gray-400 mb-0.5">持有收益率</div>
          <div className={`font-bold ${colorClass} flex items-center justify-center gap-0.5`}>
            {isUp ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
            {holding.return_pct != null
              ? `${isUp ? "+" : ""}${holding.return_pct.toFixed(2)}%`
              : "-"}
          </div>
        </div>

        <div className="text-right">
          <div className="text-[11px] text-gray-400 mb-0.5">持仓市值</div>
          <div className="text-sm font-semibold text-gray-700">
            {holding.market_value.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Sectors */}
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

      {/* Footer: cost / unrealized */}
      {holding.has_tx && (
        <div className="mt-3 pt-3 border-t border-gray-50 flex items-center justify-between text-xs">
          <div className="flex items-center gap-3 text-gray-500">
            <span>
              成本{" "}
              <span className="text-gray-700">{holding.total_cost?.toFixed(2)}</span>
            </span>
            <span>
              持有{" "}
              <span className={colorClass}>
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
```

- [ ] **Step 2: Replace inline `FundCard` in `PortfolioDashboard.tsx`**

Remove the inline `FundCard` function (and its `FundCardProps` interface). Add import at top:

```tsx
import FundCard from "../components/portfolio/FundCard";
```

The existing JSX `<FundCard key={h.fund_code} holding={h} />` keeps working without change.

Remove now-unused `TrendingUp`, `TrendingDown`, `ChevronRight`, `ShoppingCart`, `DollarSign` icons from the page-level lucide import only if they are no longer referenced elsewhere in the file (`DollarSign` is still used in the empty-state block — keep it).

- [ ] **Step 3: Verify**

```bash
docker compose exec frontend npm run lint
docker compose exec frontend npx tsc --noEmit
```

Browser: holdings list cards now show the new layout — 当日估算 (large, left) / 持有收益率 (middle) / 持仓市值 (small, right). Sector chips and 成本/持有 footer still render.

- [ ] **Step 4: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/portfolio/FundCard.tsx \
        frontend/src/pages/PortfolioDashboard.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(portfolio): restyle fund holding card to match screenshot layout"
```

---

## Task 5: Frontend — `NavChart` with week/month/year toggle

**Files:**
- Create: `frontend/src/components/fund/NavChart.tsx`

- [ ] **Step 1: Create `NavChart.tsx`**

```tsx
import { useState, useMemo } from "react";

export interface NAVPoint {
  date: string;
  nav: number;
  change_pct: number;
}

type Range = "week" | "month" | "year";

const RANGE_LABEL: Record<Range, string> = {
  week: "周",
  month: "月",
  year: "年",
};

const RANGE_DAYS: Record<Range, number> = {
  week: 5,
  month: 22,
  year: 250,
};

interface Props {
  points: NAVPoint[];
  defaultRange?: Range;
}

export default function NavChart({ points, defaultRange = "month" }: Props) {
  const [range, setRange] = useState<Range>(defaultRange);

  const sliced = useMemo(() => {
    const n = RANGE_DAYS[range];
    return points.slice(-n);
  }, [points, range]);

  if (sliced.length === 0) {
    return <div className="text-sm text-gray-400 py-8 text-center">暂无净值数据</div>;
  }

  const navValues = sliced.map((p) => p.nav);
  const minNav = Math.min(...navValues);
  const maxNav = Math.max(...navValues);
  const last = sliced[sliced.length - 1];
  const first = sliced[0];
  const periodChangePct = first.nav ? ((last.nav - first.nav) / first.nav) * 100 : 0;
  const isUp = periodChangePct >= 0;
  const strokeColor = isUp ? "#ef4444" : "#10b981";
  const fillId = isUp ? "navGradRed" : "navGradGreen";

  const W = 600;
  const H = 160;
  const PAD = 10;
  const range_v = maxNav - minNav || 1;
  const stepX = (W - PAD * 2) / (sliced.length - 1 || 1);

  const path = sliced
    .map((p, i) => {
      const x = PAD + i * stepX;
      const y = H - PAD - ((p.nav - minNav) / range_v) * (H - PAD * 2);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  const areaPath = `${path} L${(PAD + (sliced.length - 1) * stepX).toFixed(1)} ${H - PAD} L${PAD} ${H - PAD} Z`;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-gray-500">
          区间涨幅{" "}
          <span className={isUp ? "text-red-600 font-medium" : "text-emerald-600 font-medium"}>
            {isUp ? "+" : ""}
            {periodChangePct.toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-1 bg-gray-50 rounded-lg p-0.5">
          {(["week", "month", "year"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
                range === r
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {RANGE_LABEL[r]}
            </button>
          ))}
        </div>
      </div>

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
        <path
          d={path}
          fill="none"
          stroke={strokeColor}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
      </svg>

      <div className="grid grid-cols-2 mt-2 text-xs text-gray-500">
        <div>
          最低 <span className="text-gray-700 font-medium">{minNav.toFixed(4)}</span>
        </div>
        <div className="text-right">
          最高 <span className="text-gray-700 font-medium">{maxNav.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build (no usage yet)**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

Expected: no errors. (Component will be wired up in Task 8 / Task 9.)

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/fund/NavChart.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(fund): add NavChart component with week/month/year toggle"
```

---

## Task 6: Frontend — `TransactionList`

**Files:**
- Create: `frontend/src/components/fund/TransactionList.tsx`

- [ ] **Step 1: Create `TransactionList.tsx`**

```tsx
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
```

- [ ] **Step 2: Verify build**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/fund/TransactionList.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(fund): add per-fund TransactionList component"
```

---

## Task 7: Frontend — `MyHoldingTab`

**Files:**
- Create: `frontend/src/components/fund/MyHoldingTab.tsx`

- [ ] **Step 1: Create `MyHoldingTab.tsx`**

```tsx
import NavChart, { type NAVPoint } from "./NavChart";
import TransactionList from "./TransactionList";

export interface FundHoldingSummary {
  total_shares: number;
  total_cost: number;
  market_value?: number;
  unrealized_pnl?: number;
  realized_pnl?: number;
  total_return_pct?: number;
}

interface Props {
  fundCode: string;
  summary: FundHoldingSummary | null;
  navHistory: NAVPoint[];
}

export default function MyHoldingTab({ fundCode, summary, navHistory }: Props) {
  const totalReturn =
    (summary?.unrealized_pnl ?? 0) + (summary?.realized_pnl ?? 0);
  const isUp = totalReturn >= 0;
  const colorClass = isUp ? "text-red-600" : "text-emerald-600";

  return (
    <div className="space-y-4">
      {/* Holding summary */}
      {summary && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-4">持仓概览</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="text-xs text-gray-400 mb-1">持有份额</div>
              <div className="font-semibold text-gray-900">
                {summary.total_shares.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">持有成本</div>
              <div className="font-semibold text-gray-900">
                ¥{summary.total_cost.toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">当前市值</div>
              <div className="font-semibold text-gray-900">
                ¥{(summary.market_value ?? 0).toFixed(2)}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-400 mb-1">累计收益</div>
              <div className={`font-semibold ${colorClass}`}>
                {isUp ? "+" : ""}¥{totalReturn.toFixed(2)}
                {summary.total_return_pct != null && (
                  <span className="text-xs ml-1">
                    ({isUp ? "+" : ""}
                    {summary.total_return_pct.toFixed(2)}%)
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* NAV chart */}
      {navHistory.length > 0 && (
        <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
          <h3 className="font-semibold text-gray-900 mb-2">单位净值走势</h3>
          <NavChart points={navHistory} defaultRange="month" />
        </div>
      )}

      {/* Transactions */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
        <h3 className="font-semibold text-gray-900 mb-1">历史交易</h3>
        <TransactionList fundCode={fundCode} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/fund/MyHoldingTab.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(fund): add MyHoldingTab with summary, chart and transactions"
```

---

## Task 8: Frontend — `FundInfoTab`

**Files:**
- Create: `frontend/src/components/fund/FundInfoTab.tsx`

- [ ] **Step 1: Create `FundInfoTab.tsx`**

```tsx
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
```

- [ ] **Step 2: Verify build**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/components/fund/FundInfoTab.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(fund): add FundInfoTab with chart, top holdings and basic info"
```

---

## Task 9: Frontend — wire tabs into `FundDetailPage`

**Files:**
- Modify: `frontend/src/pages/FundDetailPage.tsx`

- [ ] **Step 1: Rewrite `FundDetailPage.tsx`**

Replace the entire file with:

```tsx
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

  // Fetch per-fund summary (decides whether 我的持仓 tab shows)
  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/transactions/summary`, {
      headers: { "Content-Type": "application/json" },
    })
      .then((r) => (r.ok ? r.json() : { funds: [] }))
      .then((d) => {
        if (cancelled) return;
        const match = (d.funds as SummaryFund[] | undefined)?.find(
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
```

- [ ] **Step 2: Verify**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

Browser:
- Open a fund you hold via the overview page → 我的持仓 tab is selected, shows holding summary, NAV chart with month default + week/month/year toggle, and history transactions.
- Open a fund you do NOT hold (search a 6-digit code your account doesn't own — easiest path: temporarily remove a holding and reopen): 我的持仓 tab is hidden, 基金资料 tab is selected by default and shows top holdings + basic info.
- Switch tabs — both render correctly. Range toggle on the chart works.

- [ ] **Step 3: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/pages/FundDetailPage.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "feat(fund): tabbed detail page with my-holding and fund-info tabs"
```

---

## Task 10: Frontend — sanity-check `PortfolioDashboard.tsx` size + cleanup

**Files:**
- Modify: `frontend/src/pages/PortfolioDashboard.tsx`

- [ ] **Step 1: Check line count**

```bash
wc -l frontend/src/pages/PortfolioDashboard.tsx
```

Expected: well under 500 (the inline `FundCard` + `AddHoldingModal` + hero block are all extracted by now).

- [ ] **Step 2: Remove now-unused imports**

Open `PortfolioDashboard.tsx`, remove from the `lucide-react` import any of `RefreshCw`, `TrendingUp`, `TrendingDown`, `ChevronRight`, `ShoppingCart` that no longer appear in the file. Keep what is still referenced (likely `Camera`, `Plus`, `DollarSign`, `X`).

- [ ] **Step 3: Verify**

```bash
docker compose exec frontend npx tsc --noEmit
docker compose exec frontend npm run lint
```

- [ ] **Step 4: Bump version & commit**

```bash
./scripts/bump-version.sh frontend patch
git add frontend/src/pages/PortfolioDashboard.tsx \
        frontend/package.json docs/project/versions/frontend/CHANGELOG.md
git commit -m "chore(portfolio): drop unused icon imports after extraction"
```

---

## Task 11: End-to-end verification

**Files:** none

- [ ] **Step 1: Restart full stack**

```bash
docker compose down
make dev
```

- [ ] **Step 2: Manual browser checks**

Login (`allenpan / admin123` per CLAUDE.md). Verify on the overview page:

1. Hero: total assets + 今日估算 + 持有收益率 visible. 「展开明细 ▾」 toggles the unrealized/realized block.
2. Three quick actions (截图导入 / 添加持仓 / AI 分析) still functional — at minimum click each and confirm the existing modal/flow opens.
3. Holding cards: new layout (当日估算 left big / 持有收益率 middle / 持仓市值 right). Sector chips + 成本/持有 footer still present for held funds.

Click a held fund:

4. Detail page hero unchanged.
5. 我的持仓 tab is the default. Shows: 持仓概览 (4 cells) + NAV chart (week/month/year toggle, default month) + 历史交易 list.
6. Switch range to 周 / 年 — chart redraws with fewer / more points and updated min/max + 区间涨幅.
7. Switch to 基金资料 tab — chart + 十大重仓股 + 基金概况 render.

For a fund the user does **not** hold (e.g. open detail by entering an unheld code via existing flow, or temporarily delete a holding):

8. 我的持仓 tab hidden; 基金资料 tab selected; no errors in console.

- [ ] **Step 3: Push branch**

```bash
git push -u origin users/haowen/portfolio-fund-redesign
```

- [ ] **Step 4: Open PR**

```bash
gh pr create \
  --base main \
  --title "feat(ui): portfolio dashboard & fund detail page redesign" \
  --body "$(cat <<'EOF'
## Summary
- Restyles holding cards to match Alipay-style screenshot
- Hero card P&L breakdown collapsible (default collapsed)
- Fund detail page split into 我的持仓 / 基金资料 tabs
- NAV chart gets week/month/year toggle (default month)
- Per-fund transaction history visible in 我的持仓 tab
- Backend: `/api/funds/{code}` now returns ~250 days of NAV history

## Spec
docs/superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md

## Test plan
- [x] Manual browser verification (overview + detail flows)
- [x] tsc + eslint clean
- [x] No backend test changes (only constant tweak)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review

**Spec coverage**

| Spec section | Covered by |
|---|---|
| §1 Hero collapsible P&L | Task 3 |
| §1 Three quick actions kept | (no change — verified Task 11) |
| §1 New FundCard layout | Task 4 |
| §2 Tabs in detail page | Task 9 |
| §2 MyHoldingTab (summary + chart + tx list) | Tasks 5, 6, 7 + wired in 9 |
| §2 FundInfoTab (chart + holdings + info) | Tasks 5, 8 + wired in 9 |
| §2 No buy/sell buttons | (omission — nothing added) |
| §3 NAV history extended | Task 1 |
| §3 `/api/transactions?fund_code=` filter | Already exists in backend (verified during planning). No task needed. |
| §4 Component split | Tasks 2, 3, 4, 5, 6, 7, 8 |

**Placeholder scan:** all steps have concrete file paths, code, or commands. No "TBD" / "fill in" / "similar to". The one approximate value is `length around 250` for the AkShare response, which is intentional (AkShare may return fewer points for new funds).

**Type consistency:** `NAVPoint` is defined and exported from `NavChart.tsx`, then imported in `MyHoldingTab.tsx`, `FundInfoTab.tsx`, `FundDetailPage.tsx`. `FundHoldingSummary` defined and exported from `MyHoldingTab.tsx`, used in `FundDetailPage.tsx`. `TopHolding` defined and exported from `FundInfoTab.tsx`, used in `FundDetailPage.tsx`. `FundCardHolding` defined and exported from `FundCard.tsx` — `PortfolioDashboard.tsx`'s `mergedHoldings` shape matches it (string-name lookup, all required keys present).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-portfolio-fund-detail-redesign.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
