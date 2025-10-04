# AI Automation Workflow and Pipeline

## Trigger Sources

- Push / PR
- Nightly scheduled scan
- New issue labeled `ai-fix`
- Failing regression scenario

## Detection Layer (ai/detectors/)

### Static Analysis
- AST & pattern rules (performance anti-patterns, library misuse)
- Test failure parser (map stack trace → probable module)
- Regression diff comparator (image hash delta, numeric tolerance exceed)
- Dependency vulnerability ingest (GitHub Advisory → map to requirements)

### Classification & Root Cause
- Scoring heuristic: (confidence, blast_radius, complexity)
- If confidence > threshold → proceed to patch generation

## Patch Generation (ai/patch_generators/)

- Creates branch: `ai/fix/<issue-or-hash>`
- Generates unified diff (enforces small scope)
- Inserts/updates tests (unit or regression scenario) when missing
- Updates change doc stub in `changes/<date>-<tag>.md`

## Validation Sandbox (ai/sandbox/)

- Build container
- Run: lint → type check → unit tests → integration tests → focused regression cases
- Compute metrics delta (runtime, memory, image size)

## PR Creation (ai/pr_agent/)

**Title**: `fix: <short summary> (AI Auto)`

**Body sections**:
- Problem
- Root Cause
- Proposed Fix
- Tests Added
- Risk
- Rollback

**Attaches artifacts**: before/after metrics, failing test reproduction log

## Human Review Assist

- Labels: `ai-generated`, `needs-review`
- Reviewer suggestions from CODEOWNERS mapping
- If low risk + high confidence & passes gating policies → optional auto-merge rule

## Post-Merge

- `changes/` doc file kept
- SBOM & dependency diff appended to PR comments (optional)
- Regression baselines updated only if fix explicitly marked `baselines:update`

## Change Documentation (changes/*.md Template)

### Front Matter
```yaml
date: 2025-09-20
id: ISSUE-123
type: bugfix
area: backend.analysis
ai_generated: true
confidence: 0.86
```

### Sections
1. Question (Observed Problem)
2. Root Cause Analysis
3. Resolution Approach
4. Patch Summary (files touched)
5. Tests Added / Updated
6. Metrics Before vs After
7. Risk & Mitigations
8. Rollback Plan
9. Follow-ups

## Test Strategy

### Unit Tests
- **Scope**: Pure functions (analysis calculations)
- **Execution**: Fast, parallel, run every commit

### Integration Tests
- **Scope**: API endpoints (mock external I/O), storage abstraction
- **Execution**: Run on PR

### Regression Tests
- **Golden JSON**: Analysis output comparison
- **Image SSIM**: Structural similarity or hash (permissible delta threshold)
- **Performance Budget**: Assertions (e.g., chart gen < 5s)

### Failure Handling
- If regression drift small & intentional → require baseline update tag in PR
- Large drift blocks merge

## CI/CD Pipeline (GitHub Actions)

### backend-ci.yml
1. Checkout
2. Cache deps
3. Lint (ruff) + Type check (mypy)
4. Unit tests
5. Integration tests
6. Build image
7. Trivy scan
8. Upload coverage + OpenAPI spec

### regression-benchmark.yml
- **Trigger**: nightly, manual, or label
- Run regression tests
- Compare to baselines
- Post summary comment / open issue if drift

### nightly-ai-audit.yml
- Run detectors
- Attempt auto-fixes (up to N)
- Open PRs

### deploy-prod.yml (manual approval)
1. Pull image digest from build
2. Verify signature (cosign)
3. Apply k8s manifests (kubectl or helm)
4. Run smoke tests (probe /health)
5. Canary route % traffic (progressive) if using service mesh/ALB weighting

### auto-fix-pr.yml
- On labeled issue `ai-fix` → run patch generator pipeline

### frontend-ci.yml
1. Lint (eslint)
2. Type check (tsc)
3. Unit tests (vitest / jest)
4. Build
5. Upload static artifacts → OSS
6. Invalidate CDN (if prod & approved)

## Regression Baseline Handling

### Storage Structure
```
backend/tests/regression/baselines/
├── scenario-id/
│   ├── input.json
│   ├── expected_analysis.json
│   └── expected_chart.hash (or .png for manual diff)
```

### Update Process
- `update_baselines.py` script compares & writes new baseline with explicit flag
- AI agent never overwrites baselines without `baseline-update` intent

## Security & Governance

### Policies
- OPA / Conftest on k8s manifests (infrastructure/security)
- Dependency allowlist & banned patterns
- Secret scanning pre-merge
- Signed images + provenance (SLSA level attempt)

### AI Guardrails
- Patch size limit (e.g., < 400 lines changed)
- No changes to `infra/` or `security/` directories unless labeled `infrastructure-change`
- Require human approval if touching auth, storage, or financial calculation core modules

## Observability as Code

- `grafana-dashboards/*.json` versioned
- `alert-rules/*.yaml` synced to cluster (GitOps)
- `logging-parsers/` for structured log ingestion

## Development Workflow Summary

```
dev → branch → push → CI (lint+tests) → PR (manual or AI) → review → merge
  → build & sign → deploy staging → regression → promote prod
```

## Recommended Next Steps

1. Create new directories (`ai/`, `changes/`)
2. Add regression test harness + baseline format
3. Add initial GitHub Actions workflows skeleton
4. Implement minimal AI detector (e.g., failing test root cause stub)
