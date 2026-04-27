# Contributing to Fund Agent

Fund Agent is a personal-use project — single user, local docker-compose only. The contribution guidelines below assume you're either the original developer or a forked-and-customizing user. There's no public CI deploy and no production cluster to break.

## Prerequisites

- Docker Desktop (Compose v2)
- Python 3.12, Node 20+ (for IDE tooling outside the container)
- VS Code with **Agent Maestro** extension running on `localhost:23333` — the backend routes every LLM call through it

## Initial Setup

```bash
git clone https://github.com/<you>/FundAgent.git
cd FundAgent

pip install pre-commit && pre-commit install

make dev                                    # docker compose up
curl http://localhost:8000/api/health        # smoke check
```

See [docs/development/getting-started.md](docs/development/getting-started.md) for first-login + common gotchas.

## Workflow

```bash
# 1. Branch
git checkout -b users/<you>/<short-feature-name>
# Branch name must match users/{user}/{feature} (enforced in CI on PR).

# 2. Make changes, then verify
cd backend && make test && make lint
docker compose exec frontend npm run lint && npm test
make fmt

# 3. Bump version (pre-commit enforces this)
./scripts/bump-version.sh backend patch
# or
./scripts/bump-version.sh frontend minor

# 4. Update CHANGELOG entry
#    docs/project/versions/backend/CHANGELOG.md
#    docs/project/versions/frontend/CHANGELOG.md

# 5. Commit
git add . && git commit -m "feat(scope): subject"
```

### Commit Message Format

```
<type>(<scope>): <subject>

<body>
```

`type` ∈ `feat | fix | docs | refactor | test | chore`. Examples:

```
feat(portfolio): collapsible P&L breakdown in HeroCard
fix(crawler): respect eastmoney rate limit on cold cache
docs(architecture): rewrite database-schema for v0.12
```

## Coding Standards

### Python

- **Black** (120-col), **Ruff**, **mypy**
- Type hints on all functions
- pytest, async tests use `@pytest.mark.asyncio`
- Max 500 lines per file (pre-commit enforces)
- One repository per MongoDB collection under `backend/src/database/repositories/`

### TypeScript

- **Prettier**, **ESLint** (incl. `eslint-plugin-security`, `eslint-plugin-perf-standard`)
- TypeScript strict mode; no `any` (use `unknown`)
- Functional components + hooks; no `console.log` in production builds
- Vitest + React Testing Library

See [docs/development/coding-standards.md](docs/development/coding-standards.md) for details.

## Pre-Commit Checklist

- [ ] Tested locally — actually clicked through the flow in the browser
- [ ] `make fmt && make test && make lint` clean
- [ ] Bumped version (`./scripts/bump-version.sh`)
- [ ] CHANGELOG updated
- [ ] Pydantic ↔ TypeScript contracts aligned
- [ ] No secrets in diff: `git diff --staged | grep -iE 'key|secret|password|token'`

## Pull Request Process

PR title:

```
<type>(<scope>): <short subject>
```

Body:

```markdown
## Context
Why this change is needed.

## Changes
- ...

## Testing
- [ ] Unit tests pass
- [ ] Manual smoke test in docker-compose
```

CI on PR runs:
- Branch name policy
- Backend pytest
- Frontend tests
- Linting (Ruff, Black, ESLint, TypeScript, mypy)
- Version bump validation

There is **no auto-deploy on merge.** This project doesn't have a production cluster. If you maintain your own deployment, deploy manually after merge.

## Versioning

[Semantic versioning](https://semver.org/): `MAJOR.MINOR.PATCH`. Backend and frontend version independently.

- Per-version CHANGELOG entries: `docs/project/versions/{backend,frontend}/CHANGELOG.md`
- Compatibility matrix: `docs/project/versions/VERSION_MATRIX.md`

## Documentation

When you change behavior, update docs in the same PR:

- **New feature** → spec under `docs/features/<name>.md` (use [`docs/features/README.md`](docs/features/README.md) as template)
- **Architectural change** → update `docs/architecture/`
- **Recurring issue** → add a note under `docs/troubleshooting/`
- **Database change** → update `docs/architecture/database-schema.md`

When you delete a feature, delete (or archive) its docs in the same PR.

## Getting Help

- [docs/README.md](docs/README.md) — documentation index
- [CLAUDE.md](CLAUDE.md) — quick rules, env-var gotcha
- [docs/troubleshooting/](docs/troubleshooting/)

---

Personal project — keep things tight, delete fearlessly, prefer simple fixes.
