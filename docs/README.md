# Fund Agent Documentation

Personal-use AI assistant for Chinese onshore mutual funds (场外基金).

---

## Current Status

| Component | Version | Environment |
|---|---|---|
| Backend | v0.12.1 | Local docker-compose |
| Frontend | v0.13.0 | Local docker-compose |

> Single-user, runs on your own machine. No production cluster. See [CLAUDE.md → Environment](../CLAUDE.md#-environment).

---

## Start Here

- [CLAUDE.md](../CLAUDE.md) — development rules, quick commands, env-var gotcha
- [Getting Started](development/getting-started.md) — clone → `make dev` → first login
- [PRD](prd.md) — what Fund Agent does, in one page
- [System Design](architecture/system-design.md) — backend + frontend layout
- [Agent Architecture](architecture/agent-architecture.md) — LangGraph, sub-agents, tools
- [Database Schema](architecture/database-schema.md) — MongoDB collections

## By Category

### Architecture
- [System Design](architecture/system-design.md)
- [Agent Architecture](architecture/agent-architecture.md)
- [Database Schema](architecture/database-schema.md)

### Development
- [Getting Started](development/getting-started.md)
- [Coding Standards](development/coding-standards.md)
- [Testing Strategy](development/testing-strategy.md)
- [Verification](development/verification.md)
- [Error Handling](development/error-handling.md)

### Deployment
- [Cosmos DB / MongoDB API Compatibility](deployment/cosmos-db-mongodb-compatibility.md) — kept in case you point `MONGODB_URL` at Cosmos

### Features
- [Feature Specs Guide](features/README.md)
- [Admin Health Dashboard](features/admin-health-dashboard.md)

### Testing
- [E2E Automation Guide](testing/e2e-automation-guide.md)
- [E2E Reference](testing/e2e-reference.md)
- [Unit Test Coverage Report](testing/unit-test-coverage-report.md)
- [TestSprite Setup](testing/testsprite-setup.md)

### Troubleshooting
- [Troubleshooting Index](troubleshooting/README.md)
- [Docker Env Reload Issue](troubleshooting/docker-env-reload-issue.md) — 🚨 read this once
- [CORS / API Connectivity](troubleshooting/cors-api-connectivity.md)
- [Frontend Issues](troubleshooting/frontend-issues.md)
- [MongoDB / Cosmos DB](troubleshooting/mongodb-cosmos-db.md)
- [Streaming Issues](troubleshooting/streaming-issues.md)
- [Data Validation Issues](troubleshooting/data-validation-issues.md)
- [Transaction Reconciliation Datetime Fix](troubleshooting/transaction-reconciliation-datetime-fix.md)

### Project
- [Version Management](project/versions/README.md)
- [Backend CHANGELOG](project/versions/backend/CHANGELOG.md)
- [Frontend CHANGELOG](project/versions/frontend/CHANGELOG.md)
- [Specifications](project/specifications.md)

### Specs / Plans
- [2026-04-24 — FundAgent rebrand spec](specs/2026-04-24-fundagent-design.md)
- [2026-04-27 — Portfolio + Fund Detail Redesign spec](superpowers/specs/2026-04-27-portfolio-fund-detail-redesign-design.md)
- [2026-04-27 — Portfolio + Fund Detail Redesign plan](superpowers/plans/2026-04-27-portfolio-fund-detail-redesign.md)

---

## Documentation Standards

- Max 500 lines per file.
- Active docs live under top-level `docs/` subdirectories. Historical snapshots go under `docs/archive/`.
- When you delete a feature in code, delete (or archive) its docs in the same PR.
