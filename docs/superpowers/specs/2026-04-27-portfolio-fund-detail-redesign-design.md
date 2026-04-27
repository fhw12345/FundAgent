# Portfolio Dashboard & Fund Detail Page Redesign

**Date:** 2026-04-27
**Status:** Approved (brainstorming)
**Scope:** Frontend (PortfolioDashboard, FundDetailPage) + minor backend extensions

## Background

Two reference screenshots from a target Alipay-style fund app define the desired
look-and-feel:

1. **Overview** — clean hero (total assets / today's estimate / total return),
   simple holding cards (today's estimate, return %, sector chips).
2. **Fund Detail** — large NAV with today's estimate, sector chips, holding
   summary (shares/cost/return), NAV trend chart with week/month/year toggle,
   transaction history list, action buttons (DCA/sell/buy).

Current implementation already covers the fundamentals (hero card, sector chips,
NAV chart, top-holdings, basic info). This redesign closes the gaps so that both
pages match the screenshots' layout and density while keeping all current
features the user explicitly wants to keep.

## Goals

- Overview page card layout matches the screenshot (today's estimate prominent,
  return %, sectors).
- Hero card P&L breakdown becomes collapsible to reduce visual noise by default.
- Fund detail page splits content into "我的持仓" / "基金资料" tabs.
- NAV chart supports week/month/year switching, default month, single network
  request.
- Per-fund transaction history visible inside the detail page.
- All file sizes stay under the 500-line pre-commit limit by splitting into
  focused components.

## Non-Goals

- No buy/sell/DCA action buttons in this iteration (read-only history only).
- No new screenshot import / add-holding / AI flows; existing three quick-action
  buttons are kept as-is.
- No backend rewrite of `/api/transactions/summary`; only minor query support
  added if missing.
- No mobile-vs-desktop divergence beyond what already exists (Tailwind
  breakpoints).

## Decisions Locked During Brainstorming

| ID | Question | Decision |
|----|----------|----------|
| Q1 | Keep the three quick-action buttons (screenshot import / add holding / AI analysis)? | **B** — keep, only restyle cards. |
| Q2 | How to combine personal-holding view with fund-info view in detail page? | **C** — two tabs ("我的持仓" / "基金资料"). |
| Q3 | NAV chart range switching strategy? | **A** — backend returns 1 year, frontend slices client-side. |
| Q4 | Buy/sell action buttons + transaction list? | **B** — show transaction list, **no** buy/sell buttons. |
| Q5 | Hero card P&L three-column block? | **C** — collapsible (default collapsed). |
| Q6 | Default range + switch granularity for NAV chart? | **A** — default "month", toggle week/month/year. |

## Design

### §1 Overview Page (PortfolioDashboard)

**Hero card**
- Top row: 基金总资产 (large) + 今日估算 (existing) + 持有收益率.
- 「未实现盈亏 / 已实现盈亏 / 持有收益率」 three-column block becomes
  collapsible. Default collapsed; a small toggle (e.g. "展开明细 ▾") expands.
- Refresh button stays in top-right.

**Quick actions**
- Three buttons unchanged: 截图导入 / 添加持仓 / AI 分析.

**Holding card (FundCard) — new layout**
- Header row: fund code (mono small) + 已建仓 badge (when applicable) + fund
  name + ChevronRight.
- Data row, three columns:
  - **Left:** 当日估算 — percentage (large, colored) + ¥ amount (small).
  - **Middle:** 持有收益率 — percentage with trend icon, colored.
  - **Right:** 持仓市值 — number (smaller, secondary color).
- Sector chips row (existing) preserved below.
- Cost / unrealized P&L footer row (existing) preserved when `has_tx` is true.

### §2 Fund Detail Page (FundDetailPage)

**Header & hero card** — unchanged.

**Tabs** — new component below hero. Two tabs:

- **我的持仓** (default if user has transactions for this fund; otherwise hidden
  and 基金资料 becomes the only/active tab)
  1. **Holding summary card:** 持有份额 / 持有成本 / 当前市值 / 累计收益
     (amount + percentage). Source: `/api/transactions/summary` filtered to this
     fund.
  2. **NAV chart:** week/month/year toggle, default **month**.
  3. **Transaction history list:** date / type (申购/赎回/分红) / shares /
     amount / status. Date-descending, max 50 rows.

- **基金资料**
  1. **NAV chart:** same component (range toggle).
  2. **十大重仓股** — preserved from current implementation.
  3. **基金概况** — preserved from current implementation.

**No buy/sell/DCA buttons** in this iteration.

### §3 Backend Changes

**`GET /api/funds/{code}` — extend NAV history**
- Change to return ~1 year of trading days (≈ 250 points).
- Schema unchanged (`nav_history: NAVPoint[]`).
- Frontend slices: week = last 5, month = last 22, year = all.

**`GET /api/transactions?fund_code=xxx` — per-fund filter**
- Inspect existing `backend/src/api/transactions.py`. If a `fund_code` query
  parameter is not yet supported, add it as an optional filter.
- Returns existing transaction shape: `date, type, shares, amount, status`.
- Sort date desc, limit 50.

**`GET /api/transactions/summary`** — unchanged.

### §4 Component Split

To keep all files under the 500-line pre-commit limit:

| File | Responsibility |
|------|---------------|
| `pages/PortfolioDashboard.tsx` | Page-level: data fetching, layout, modals (slim). |
| `components/portfolio/HeroCard.tsx` | Hero card with collapsible P&L breakdown. |
| `components/portfolio/FundCard.tsx` | New holding card layout. |
| `components/portfolio/AddHoldingModal.tsx` | Existing modal extracted. |
| `pages/FundDetailPage.tsx` | Page-level: data fetching, tab state, layout. |
| `components/fund/MyHoldingTab.tsx` | Holding summary + NAV chart + transaction list. |
| `components/fund/FundInfoTab.tsx` | NAV chart + top holdings + basic info. |
| `components/fund/NavChart.tsx` | Reusable chart with week/month/year toggle props. |
| `components/fund/TransactionList.tsx` | Per-fund transaction list rendering. |

### Data Flow Summary

```
PortfolioDashboard
  ├─ GET /api/transactions/summary  → summaries (per-fund totals)
  ├─ GET /api/portfolio             → snapshot fallback
  └─ render: HeroCard + actions + FundCard[]

FundDetailPage(fundCode)
  ├─ GET /api/funds/{code}          → 1yr nav_history + top_holdings + basic_info
  ├─ GET /api/transactions/summary  → pick this fund's summary (for holding card)
  ├─ GET /api/transactions?fund_code=xxx → tx history (lazy on tab open or on mount)
  └─ render: tabs → MyHoldingTab | FundInfoTab
```

### Error Handling

- Network errors per request surface inline (existing pattern: red toast / inline
  error block).
- Missing transactions for a fund: hide 我的持仓 tab, default to 基金资料.
- NAV history < requested slice length: render whatever is available without
  error.

### Testing

- Frontend: rely on existing eslint + tsc + vitest setup. Add minimal smoke
  tests for tab switching and chart range slicing if feasible; otherwise verify
  via local docker-compose + browser per CLAUDE.md rules.
- Backend: if `fund_code` filter is added to `/api/transactions`, add a unit
  test in `backend/tests/`.
