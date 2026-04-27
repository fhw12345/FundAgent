# Fund Agent — Agent Architecture

This document describes how Fund Agent orchestrates LLM calls, sub-agents, and tools. Code lives under `backend/src/agent/`.

## High-Level

Two flows coexist:

1. **Simple chat** (`chat_agent.py`) — direct streaming chat with persisted message history.
2. **ReAct agent** (`langgraph_react_agent.py`) — LangGraph state machine with a tool loop. The "deep" variant (`deep_react_agent.py`) adds a cross-vendor debate phase.

All LLM calls funnel through `llm_client.py`, which routes per role to a model and provider via the local **Agent Maestro** proxy on `localhost:23333`. The proxy holds the user's API keys; the backend never sees them directly.

## Per-Role Model Routing

| Role | Default model | Vendor |
|---|---|---|
| Main analyst | `claude-opus-4-7` | Anthropic |
| Fundamentals / vision (screenshot import) | `gpt-5.4` | OpenAI |
| News | `gemini-3.1-pro-preview` | Google |
| Debater | `gemini-3.1-pro-preview` | Google |
| PDF / quarterly report | `gemini-3.1-pro-preview` | Google (long context) |

The debater is required to use a **different vendor** than the main analyst — this enforces the cross-vendor independence that motivates the multi-LLM design.

## Sub-Agents

Under `backend/src/agent/subagents/`:

- **`financial.py`** — fund-level fundamentals: NAV trends, holdings, manager info, sector exposure, fund-type-specific framing.
- **`technical.py`** — purely chart / NAV-pattern reasoning over historical NAV series (no Fibonacci / Stochastic — those were removed in the rebrand).
- **`news.py`** — recent news and macro context for the underlying sectors / themes a fund is exposed to.
- **`debater.py`** — independent verifier. Reads the main verdict, raises structured concerns (`debate_types.py`: `Concern`, `Rebuttal`), forces the main analyst to rebut, then a verdict node merges the verified facts.

Each sub-agent has a `SKILL.md` under `backend/src/agent/skills/` describing its tools, scope, and output contract.

## Tools

Under `backend/src/agent/tools/`:

- **`akshare_fund_tools.py`** — primary fund data: `fund_individual_basic_info_xq`, `fund_open_fund_info_em` (NAV history), `fund_portfolio_hold_em` (top holdings), fund rankings, manager info, macro indicators.
- **`eastmoney_tools.py`** — supplementary tools backed by the polite crawler in `services/eastmoney_crawler.py`. Used when AkShare lacks a field or rate-limits.
- **`analysis_cache.py`** — Redis-backed memoization for expensive multi-step analyses, keyed by (fund_code, analysis_type, date).
- **`categorization.py`** — sector/category classifier for funds based on holdings.

There is **no** Alpha Vantage, Alpaca, yfinance, EXA, or FRED tooling — all removed in the rebrand (commit `c6e45f3`).

## Deep ReAct Flow

```
                user prompt
                     │
                     ▼
            ┌─────────────────┐
            │  main_agent     │  Claude Opus 4.7 + tools
            │  (research +    │
            │   initial draft)│
            └────────┬────────┘
                     │  draft verdict
                     ▼
            ┌─────────────────┐
            │  debate_node    │  Gemini 3.1 Pro
            │  parses Concerns│  → independent verification with its own tools
            └────────┬────────┘
                     │  list[Concern]
                     ▼
            ┌─────────────────┐
            │  should_continue│
            └────────┬────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
  ┌───────────┐             ┌─────────────┐
  │  rebuttal │             │  verdict    │
  │  back to  │             │  merge facts│
  │  main_    │             │  + concerns │
  │  agent    │             │  → final    │
  └─────┬─────┘             └─────────────┘
        │
        └────► loops back into debate
```

Implementation: `backend/src/agent/deep_react_agent.py`. Extended SSE event schemas (`deep_rebuttal_start`, `deep_rebuttal_result`) stream debate state to the frontend so the UI can show concerns and rebuttals in real time.

## State Persistence

- Chat history: MongoDB `chats` + `messages` collections, with `MessageRepository` and `ChatRepository`.
- Background analysis runs: `job_runs` collection (one document per run), repository in `database/repositories/job_run_repository.py`.
- Analysis result cache: Redis (TTL on the order of hours, longer for expensive deep flows).

## Where to Look in Code

| Concern | Path |
|---|---|
| Add a new tool | `backend/src/agent/tools/` + register in the agent's tool list |
| Tweak per-role model | `backend/src/agent/llm_client.py` |
| Add a sub-agent | `backend/src/agent/subagents/<name>.py` + `skills/<name>.md` |
| Adjust debate behavior | `deep_react_agent.py` and `debate_types.py` |
| Update the chat SSE schema | `agent/chat_agent.py`, `api/chat/`, frontend `components/chat/` |
