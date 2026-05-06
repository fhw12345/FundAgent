# 今日操作建议（Today Actions）设计文档

- 日期：2026-05-06
- 状态：草稿（brainstorm 完成 1/4 节，待写实施计划）
- 关联代码：
  - `backend/src/agent/deep_react_agent.py:553-578`（verdict_prompt）
  - `backend/src/services/portfolio_service.py:144-151`（run_daily_analysis）
  - `backend/src/api/portfolio.py:158`（trigger_daily_analysis）
  - `frontend/src/pages/PortfolioDashboard.tsx`（持仓总览页）

## 背景

当前 daily analysis 对每只持仓基金独立跑一次 DeepReActAgent，输出"买入/持有/卖出"的中长期判决，但：

1. 没有把用户实际持仓上下文（成本、份额、盈亏、占比、今日估值）喂给 agent —— agent 把每只基金当成"陌生候选"研究
2. verdict 是"是否值得长期持有"，不是**今天该做什么**
3. 结果只写到每只基金的 AI 对话里，前端没有"今日操作总览"

## 目标

让用户在 portfolio 页顶部看到一张「今日操作」卡片，每只持仓显示：

- **信号徽章**：偏多 / 中性 / 偏空（中长期视角，必填）
- **执行建议**（可选）：仅当触发明确条件时出现，例如"浮盈 32%，建议止盈 50%"
- **强制重跑按钮**：节流命中时也能单只触发

点击卡片正文跳到该基金的现有 AI 对话查看完整研究报告。

## 非目标（明确不做）

- **组合层面 agent**（再平衡、行业暴露提醒）—— 留给 v2，需先做"目标配置"设置页
- **目标配置设置页**（风险偏好 / 行业上限 / 现金比例）
- **Cron 自动定时跑** —— 保持手动触发 + 智能节流
- 不引入新数据库表，沿用 `messages.metadata` JSON 字段

## 高层方案（已敲定）

| 维度 | 方案 |
|---|---|
| 持仓上下文注入 | LangGraph state 加 `holding_context` 字段，**仅 verdict_node 读取**（research/debate 阶段保持中立） |
| 输出 schema | 扁平 + 可选 `executable_action`：`{signal, signal_reason, executable_action: null \| {action, magnitude_pct, trigger}}` |
| 节流默认行为 | 全持仓任一 \|today_est_pct\| ≥ 3% **或** 上次成功运行 ≥ 4h 前 → 整体重跑；否则跳过 |
| 节流绕过 | 卡片每只基金有"强制重跑"按钮，调 `?force=true&fund_codes=xxx` |
| 节流命中响应 | HTTP 200 + `{status: "skipped", last_run_id, last_finished_at, reason}`（前端在卡片上标注"上次更新 14:23"） |
| 结构化输出格式 | verdict markdown 末尾追加 ` ```json ... ``` ` 围栏块；invoker 解析；解析失败降级为 `{signal: "中性", signal_reason: "解析失败", executable_action: null}` 并记 warning |
| 持久化 | 沿用 `chat_service.add_message`，把 `structured_verdict` 放到 `metadata.structured_verdict`；不动 mongo schema |

## 架构与数据流

```
[前端 PortfolioDashboard]
    │
    │ 1. POST /api/portfolio/daily-analysis  (无 force)
    ▼
[FastAPI trigger_daily_analysis]
    │ 2. 读 job_runs 最近一条 status in ['ok','partial']；读 portfolio 当前 est_pct
    │ 3. 节流判定: < 4h ago && 全部 |est_pct| < 3%
    │      命中 → 200 {status:"skipped", last_run_id, last_finished_at, reason:"throttled"}
    │ 4. 否则 BackgroundTask 启动 run_daily_analysis(force, fund_codes)
    ▼
[run_daily_analysis]
    │ 5. job_runs 插 running 记录
    │ 6. for each fund_code in (force 指定 || 全部持仓):
    │      a. 从 portfolio 取 holding_context
    │         {cost, shares, market_value, pnl_pct, position_pct, today_est_pct}
    │      b. agent.analyze(symbol, user_id, holding_context=...)
    │      c. invoker 解析 verdict markdown 提取 ```json``` 块 → structured_verdict
    │      d. ChatService.add_message(metadata={..., structured_verdict})
    │ 7. job_runs 收尾 (status, finished_at, fund_results)
    ▼
[DeepReActAgent]
    │ 8. AgentState 新增 holding_context: dict | None
    │ 9. research/debate/rebut 节点不读它
    │ 10. verdict_node 读它 → prompt 末尾追加 "## 用户持仓上下文" 段 + JSON schema 要求
    │ 11. verdict 输出 = 中文 markdown + ```json``` 围栏块
    ▼
[前端]
    │ 13. PortfolioDashboard 顶部 TodayActionsCard
    │     - useTodayActions() → GET /api/portfolio/today-actions
    │     - aggregation pipeline 取每只持仓最新 source=llm message 的 structured_verdict
    │     - 5 张小卡，每张：基金简称 + signal 徽章 + executable_action（若有）+ 强制重跑按钮
    │     - 点卡片正文 → 跳到该基金 AI 对话
```

## 数据模型

### `holding_context`（注入 agent 的上下文）

```python
class HoldingContext(TypedDict):
    fund_code: str
    cost_price: float           # 成本价（单位净值）
    shares: float               # 份额
    market_value: float         # 市值
    pnl_pct: float              # 浮动盈亏 %
    position_pct: float         # 持仓占比 %
    today_est_pct: float | None # 今日估算涨跌 %（可能没有）
```

### `structured_verdict`（写入 message metadata）

```python
class ExecutableAction(TypedDict):
    action: Literal["加仓", "减仓", "止盈", "止损", "换仓"]
    magnitude_pct: int          # 0-100
    trigger: str                # 触发条件说明

class StructuredVerdict(TypedDict):
    signal: Literal["偏多", "中性", "偏空"]
    signal_reason: str
    executable_action: ExecutableAction | None
```

### Verdict prompt 追加段（伪代码）

```
## 用户持仓上下文
- 你已持有 {position_pct}%（成本价 {cost_price}，份额 {shares}）
- 当前浮盈 {pnl_pct}%，今日估算 {today_est_pct}%

请在 verdict 末尾追加一段 ```json ... ``` 结构化输出：
{
  "signal": "偏多" | "中性" | "偏空",
  "signal_reason": "一句话",
  "executable_action": null | {
    "action": "加仓" | "减仓" | "止盈" | "止损" | "换仓",
    "magnitude_pct": 0-100,
    "trigger": "..."
  }
}
中性立场请将 executable_action 置 null，不要凑数。
```

### `GET /api/portfolio/today-actions` 响应

```json
{
  "items": [
    {
      "fund_code": "110011",
      "fund_name": "易方达中小盘",
      "structured_verdict": { ... },
      "verdict_at": "2026-05-06T06:23:00Z",
      "chat_id": "..."
    }
  ],
  "last_run": {
    "run_id": "...",
    "finished_at": "2026-05-06T06:23:00Z",
    "status": "ok"
  }
}
```

## 文件改动清单

### 后端

| 文件 | 改动 | 行数估计 |
|---|---|---|
| `backend/src/agent/deep_react_agent.py` | (a) `AgentState` 加 `holding_context: dict \| None`<br>(b) `analyze()` 签名加 `holding_context` 参数注入 state<br>(c) `verdict_node` 读 state，prompt 末尾追加"## 用户持仓上下文"段 + JSON 输出要求 | +60 |
| `backend/src/agent/subagent_invoker.py` | 加 `parse_structured_verdict(text) -> dict` 提取 ```json``` 围栏 | +25 |
| `backend/src/services/portfolio_service.py` | (a) `run_daily_analysis` 接收 `force, fund_codes`<br>(b) 节流判定<br>(c) 取每只基金 holding_context 传给 agent<br>(d) `add_message` metadata 加 `structured_verdict` | +90 |
| `backend/src/api/portfolio.py` | (a) `trigger_daily_analysis` 加 `force, fund_codes` query<br>(b) 节流命中返回 skipped<br>(c) 新 endpoint `GET /api/portfolio/today-actions` 用 mongo aggregation 取每持仓最新 structured_verdict | +70 |
| `backend/tests/services/test_portfolio_service.py` | 节流逻辑、强制覆盖、structured_verdict 落库的单测 | +120（新建） |

### 前端

| 文件 | 改动 |
|---|---|
| `frontend/src/types/portfolio.ts` | 加 `StructuredVerdict`, `TodayActionsResponse` 类型 |
| `frontend/src/services/portfolioApi.ts` | (a) `triggerDailyAnalysis(force, fundCodes)` 参数<br>(b) `getTodayActions()` |
| `frontend/src/hooks/useTodayActions.ts` | **新建** TanStack Query hook |
| `frontend/src/components/portfolio/TodayActionsCard.tsx` | **新建** 顶部"今日操作"卡片容器 |
| `frontend/src/components/portfolio/TodayActionItem.tsx` | **新建** 单只基金小卡（signal 徽章 + 可选 action + 强制按钮 + 跳 AI 对话） |
| `frontend/src/pages/PortfolioDashboard.tsx` | 把 `TodayActionsCard` 插在顶部；现有"分析持仓"按钮改为调 `triggerDailyAnalysis(force=false)` 并展示 skipped 提示 |

### 不改动

- `subagents/*.py`（research/debate 阶段不接触持仓）
- 数据库 schema（沿用 `messages.metadata` JSON 字段）
- agent-maestro / vendor

## 边界与失败模式

| 情况 | 处理 |
|---|---|
| LLM 没输出 ```json``` 块 | 降级为 `{signal:"中性", signal_reason:"未输出结构化字段", executable_action:null}` + log warning |
| ```json``` 块 schema 不合法（字段缺/枚举值非法） | 同上，附原始 JSON 字符串到 metadata 便于排查 |
| 节流命中但用户点了"分析持仓" | 返回 200 skipped；前端 toast 提示"距上次分析不足 4 小时且持仓波动小，已跳过。如需强制刷新请点单卡的强制按钮" |
| 单基金强制重跑期间用户又点了全量分析 | 全量按节流规则判定；单基金后台 task 互不干扰（job_runs 多条记录） |
| 用户清空了持仓 | `trigger` 已有 `if not fund_codes: 400`，沿用 |
| 持仓没有 today_est_pct（盘前/非交易日） | 节流条件 "全部 |est_pct| < 3%" 视为 0 处理，仅看 4h 时间条件 |
| 历史消息没有 structured_verdict（首次升级后） | `today-actions` 接口对该基金返回 `structured_verdict: null`；前端卡片显示"尚无分析" |

## 测试计划

### 后端单测

1. `test_throttle_skips_when_quiet_and_recent`
2. `test_throttle_runs_when_one_fund_moves_3pct`
3. `test_throttle_bypassed_by_force_param`
4. `test_force_with_fund_codes_only_runs_specified`
5. `test_holding_context_injected_into_agent_state`
6. `test_research_node_does_not_see_holding_context`（mock state 检查）
7. `test_verdict_node_includes_holding_context_in_prompt`
8. `test_parse_structured_verdict_happy_path`
9. `test_parse_structured_verdict_missing_block_returns_neutral`
10. `test_parse_structured_verdict_invalid_schema_returns_neutral`
11. `test_today_actions_aggregation_returns_latest_per_fund`

### 前端单测（vitest）

1. TodayActionsCard 渲染各 signal 徽章
2. executable_action 为 null 时不渲染执行建议块
3. 强制重跑按钮 disable during pending
4. skipped 响应正确显示"上次更新"

### 手工 e2e

1. 导入持仓 → 触发分析 → 卡片出现 5 张
2. 点强制重跑 → 单只基金 verdict 更新
3. 立刻再点全量分析 → toast 提示 skipped
4. 点卡片正文 → 跳转到该基金 AI 对话能看到完整报告

## 实施顺序（推荐）

1. **后端 schema + parser**（agent state、parse_structured_verdict + 单测）
2. **verdict prompt 改造**（追加上下文段 + JSON 要求 + e2e 验证 LLM 真的输出 JSON 块）
3. **portfolio_service 节流 + 上下文注入**（含单测）
4. **API 层 force/fund_codes 参数 + today-actions endpoint**
5. **前端类型 + hook + 卡片组件**
6. **PortfolioDashboard 集成 + skipped toast**
7. **手工 e2e + bump 版本 + CHANGELOG**

每步独立可测，可分别 commit。

## 待办（brainstorm 未完成项）

- [ ] 第 3 节：错误处理细节、超时、并发
- [ ] 第 4 节：版本号、CHANGELOG、迁移注意事项
- [ ] 写 implementation plan（writing-plans skill）

## 决策记录

| 问题 | 选择 | 理由 |
|---|---|---|
| 节流粒度 | C：默认整体跳过 + 单基金强制 | 一致快照 + 用户保有控制 |
| 上下文注入位置 | C：LangGraph state，仅 verdict_node 读 | 研究/辩论阶段保持中立判断 |
| Verdict schema | A：扁平 + 可选 executable_action | 中性立场不强行编动作 |
| 节流缓存来源 | A：复用 job_runs | 已有数据，避免双写不一致 |
| 强制重跑入口 | A：复用 endpoint + query 参数 | 一个 endpoint 涵盖三种用法 |
| 节流命中响应 | 200 + status="skipped" | 前端处理简单 |
| 结构化输出格式 | markdown ```json``` 围栏 | 用户在 chat 里也能看到原始 JSON，便于排查 |
