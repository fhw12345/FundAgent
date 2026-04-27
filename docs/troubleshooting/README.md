# Troubleshooting

Active issues only. Resolved historical incidents live under [`docs/archive/troubleshooting-history/`](../archive/troubleshooting-history/).

## 🚨 Read this once

- [Docker Env Reload Issue](docker-env-reload-issue.md) — `docker compose restart` does **not** reload `.env`. Use `--force-recreate`.

## Common issues

| Topic | When you'd hit it |
|---|---|
| [CORS / API Connectivity](cors-api-connectivity.md) | Frontend can't reach backend, CORS errors, nginx proxy weirdness |
| [Frontend Issues](frontend-issues.md) | React / TypeScript / Vite build problems |
| [MongoDB / Cosmos DB](mongodb-cosmos-db.md) | Throughput modes, indexes, NULL unique constraint quirks (only relevant if you point `MONGODB_URL` at Cosmos) |
| [Streaming Issues](streaming-issues.md) | SSE chat streaming, agent response truncation |
| [Data Validation](data-validation-issues.md) | Pydantic validation errors, request/response shape mismatches |
| [Transaction Reconciliation Datetime Fix](transaction-reconciliation-datetime-fix.md) | Datetime deprecation incident in transaction reconciliation |

## Adding a new troubleshooting note

Drop a focused markdown file in this directory with:

```markdown
## Symptom
What you observed.

## Root cause
What was actually wrong.

## Fix
The exact steps that resolved it.

## Why it happens
Optional — useful when the fix isn't obvious.
```

If the issue is one-time / no longer reproducible, archive it under `docs/archive/troubleshooting-history/` instead of cluttering active troubleshooting.
