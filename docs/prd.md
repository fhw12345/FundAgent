# Fund Agent — Product Requirements Document

> **Type**: Living document
> **Last Updated**: 2026-04-27
> **Backend**: v0.12.1 · **Frontend**: v0.13.0
> **Status**: Personal use, local-only (docker-compose)

---

## Executive Summary

**Fund Agent** is a private, single-user AI assistant for Chinese onshore mutual funds (场外基金). It helps the user manage a personal fund portfolio (持仓), import holdings from Alipay/天天基金 screenshots, run on-demand analyses with explicit 买入 / 持有 / 卖出 recommendations, and interpret fund quarterly reports.

The system is intentionally personal-scale: it runs on docker-compose, has no production cluster, no billing, no multi-tenant auth, and routes all LLM calls through a local **Agent Maestro** proxy in the user's VS Code instance.

## Product Vision

A second pair of eyes for one investor managing a CN mutual fund portfolio. Fund Agent does not place trades; it summarizes, explains, debates, and surfaces decisions for the user to act on through their own broker (Alipay / 天天基金 / 蛋卷 / etc).

## Users

A single user — the developer running the project on their own machine. No registration flow. Auth is a simplified single-user JWT.

## Core Capabilities

### 1. Portfolio Management
- Manual entry of holdings (基金代码, shares, cost basis).
- **Screenshot import**: GPT-5.4 vision parses Alipay / 天天基金 portfolio screenshots into `holdings`.
- Transaction tracking (买入 / 卖出 / 分红再投), cost basis recomputed via `cost_basis` service.
- DCA (定投) plan management with scheduled reminders.

### 2. Fund Detail
- Per-fund page with NAV trend (week / month / year toggle, ~250 trading days backing data), top holdings, sector exposure, basic info, manager info, fund type.
- Personal holding tab: shares / cost / return / P&L + per-fund transaction history.

### 3. Multi-Vendor LLM Debate
Cross-vendor sub-agents avoid single-model bias:
- **Main analyst**: Claude Opus 4.7
- **Fundamentals / vision**: GPT-5.4
- **News / debater / PDF reader**: Gemini 3.1 Pro
- The debater always uses a different vendor than the main analyst, with concern → rebuttal → verdict structure.

All routed through `Agent Maestro` proxy at `localhost:23333` — no direct API keys in backend env.

### 4. Daily Analysis (Manual Trigger)
For each holding: aggregate NAV trend + sector context + macro signals + recent news, produce a 买入 / 持有 / 卖出 verdict with reasoning. Runs through the LangGraph orchestrator.

### 5. Quarterly Report Interpretation
Upload a fund quarterly report PDF or text → Gemini long-context interpretation → structured summary (manager view, position changes, top movers, outlook).

### 6. Conversational Chat
LangGraph ReAct agent with streaming SSE; tools include AkShare fund queries, 天天基金 crawler, sector classifier, transaction lookup.

## Out of Scope

- Real trading execution
- US-stock technical analysis (Fibonacci / Stochastic / Market Structure) — removed in rebrand
- Production multi-tenant deployment
- Credit / billing / payments
- Public feedback platform
- Real-time intraday data

## Tech Stack

See [CLAUDE.md → Tech Stack](../CLAUDE.md#tech-stack) and [docs/architecture/system-design.md](architecture/system-design.md).

## Non-Functional Requirements

- **Privacy**: Single-user, runs on the user's own machine. No telemetry leaves the box (Langfuse is optional and local).
- **Resilience**: AkShare and eastmoney rate limits respected via the polite crawler in `services/eastmoney_crawler.py`.
- **Cost**: Zero ongoing infra cost beyond the user's own LLM API spend (paid through Agent Maestro).

## References

- Rebrand spec: [docs/specs/2026-04-24-fundagent-design.md](specs/2026-04-24-fundagent-design.md)
- Most recent shipped redesign: [Portfolio + Fund Detail Redesign](superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md)
