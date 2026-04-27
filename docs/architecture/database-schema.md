# Database Schema

> **Engine**: MongoDB (local docker-compose container — `fund_agent` database).
> **Driver**: Motor (async). Pydantic models live in `backend/src/models/`. Collections are accessed through one repository per collection in `backend/src/database/repositories/`.

The schema reflects backend v0.12.1.

## Collections

| Collection | Repository | Purpose |
|---|---|---|
| `users` | `user_repository.py` | Single-user account record (the developer running the app) |
| `refresh_tokens` | `refresh_token_repository.py` | JWT refresh tokens |
| `chats` | `chat_repository.py` | Chat sessions (one per conversation thread) |
| `messages` | `message_repository.py` | Individual chat messages (user / assistant / tool / SSE events) |
| `portfolios` | `portfolio_repository.py` | A user's portfolio document with embedded `holdings[]` |
| `transactions` | `transaction_repository.py` | 买入 / 卖出 / 分红再投 events |
| `dca_plans` | (in `transaction_repository.py`) | DCA (定投) schedule definitions |
| `job_runs` | `job_run_repository.py` | Background analysis run records (status, started_at, finished_at, result) |
| `fund_sector_mapping` | `fund_sector_repository.py` | Cached sector classification per fund code |

## Document Shapes

### `users`

Single-user JWT account.

```jsonc
{
  "_id": ObjectId,
  "username": "...",
  "password_hash": "bcrypt$...",
  "created_at": ISODate
}
```

### `portfolios`

One document per user. Holdings are embedded — there is no separate `holdings` collection.

```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "holdings": [
    {
      "fund_code": "012345",
      "fund_name": "...",
      "shares": 1234.56,
      "cost_basis": 1.234,
      "sector_tags": ["..."],
      "added_at": ISODate
    }
  ],
  "updated_at": ISODate
}
```

### `transactions`

```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "fund_code": "012345",
  "type": "buy" | "sell" | "dividend_reinvest",
  "shares": Number,
  "price": Number,
  "amount": Number,
  "occurred_at": ISODate,
  "source": "manual" | "screenshot" | "dca",
  "notes": String?
}
```

`/api/transactions` supports a `fund_code` query parameter — used by the per-fund transaction list in `MyHoldingTab.tsx`.

### `dca_plans`

```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "fund_code": "012345",
  "frequency": "weekly" | "biweekly" | "monthly",
  "amount": Number,
  "next_run": ISODate,
  "active": Boolean
}
```

### `job_runs`

```jsonc
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "kind": "daily_analysis" | "tplus1" | "quarterly_report" | ...,
  "status": "queued" | "running" | "completed" | "failed",
  "started_at": ISODate,
  "finished_at": ISODate?,
  "result": Object?,
  "error": String?
}
```

### `chats` and `messages`

```jsonc
// chats
{ "_id": ObjectId, "user_id": ObjectId, "title": "...", "created_at": ISODate, "updated_at": ISODate }

// messages
{
  "_id": ObjectId,
  "chat_id": ObjectId,
  "role": "user" | "assistant" | "tool" | "system",
  "content": "...",         // or structured for tool calls
  "tool_call_id": "...",    // when role == "tool"
  "tokens": Number?,
  "created_at": ISODate
}
```

### `fund_sector_mapping`

```jsonc
{
  "_id": "012345",        // fund_code as primary key
  "sectors": ["科技", "新能源", ...],
  "classified_at": ISODate,
  "classifier_version": String
}
```

## Notes

- **No insight_snapshots / feedback / credits / comments collections.** Those existed in the pre-rebrand product and were removed in commit `c6e45f3`.
- **No insights / market-data caching collection.** Hot data lives in Redis with TTL; nothing else is durably cached.
- **Database name is configurable** via `MONGODB_URL`. The connection logic in `database/mongodb.py` validates that the database name in the URL doesn't contain query-string characters (a real bug fixed earlier — see commit log).
