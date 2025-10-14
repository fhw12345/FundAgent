# Credit System Deployment Guide

## Architecture

**Credit System** = Token-based economy for LLM usage billing
- **1 Yuan = 100 Credits**
- **1 Credit = 200 Tokens**
- **New users**: 1,000 free credits
- **Minimum balance**: 10 credits

## Components

### 1. Backend API (`/api/credits/*`, `/api/users/me`)
- User profile with credit balance
- Transaction history (paginated)
- Admin credit adjustments
- Integrated into `/api/chat/stream-v2` (credit check + billing)

### 2. Reconciliation Worker (`src/workers/reconcile_transactions.py`)
- Standalone Python script
- Finds stuck PENDING transactions (>5 minutes old)
- Completes them by finding linked messages and deducting credits
- **NOT a sidecar** - runs as Kubernetes CronJob

### 3. Frontend Components
- `CreditBalance.tsx` - Balance display with color coding
- `TransactionHistory.tsx` - Full transaction history page
- `useCredits.ts` - React Query hooks with optimistic updates

---

## Local Testing

### Start Services
```bash
# Start docker-compose (backend + MongoDB + Redis)
make dev

# Or manually
docker-compose up -d
```

### Verify Backend
```bash
# Check health
curl http://localhost:8000/api/health

# Check credit endpoints exist
curl http://localhost:8000/openapi.json | grep -o '"\/api\/.*credit.*"'
# Should show:
#   "/api/users/me"
#   "/api/credits/transactions"
#   "/api/admin/credits/adjust"
```

### Run Reconciliation Worker
```bash
# Run once manually
docker-compose exec backend python -m src.workers.reconcile_transactions

# Check output:
# - "MongoDB connected"
# - "Starting transaction reconciliation"
# - "Reconciliation worker finished successfully"
```

### Check MongoDB Data
```bash
# View users with credits
docker-compose exec -T mongodb mongosh financial_agent --eval 'db.users.find({}, {username:1, credits:1, total_tokens_used:1})'

# View transactions
docker-compose exec -T mongodb mongosh financial_agent --eval 'db.transactions.find().limit(5)'

# Check transaction indexes
docker-compose exec -T mongodb mongosh financial_agent --eval 'db.transactions.getIndexes()'
```

---

## Kubernetes Deployment

### Prerequisites
- Backend image built with version tag (e.g., `test-v0.5.4`)
- MongoDB connection string in External Secrets
- DashScope API key in External Secrets

### Deploy CronJob
```bash
# Preview manifests
kubectl kustomize .pipeline/k8s/overlays/test | grep -A 50 "kind: CronJob"

# Apply to cluster
kubectl apply -k .pipeline/k8s/overlays/test

# Verify CronJob created
kubectl get cronjobs -n klinematrix-test
# Should show: reconcile-transactions

# Check schedule
kubectl get cronjob reconcile-transactions -n klinematrix-test -o yaml | grep schedule
# Should show: "*/10 * * * *" (every 10 minutes)
```

### Monitor CronJob
```bash
# Watch for job runs
kubectl get jobs -n klinematrix-test -w

# View logs from latest job
kubectl logs -n klinematrix-test -l app=reconcile-transactions --tail=100

# Check job history
kubectl get jobs -n klinematrix-test -l app=reconcile-transactions

# Manual trigger (for testing)
kubectl create job --from=cronjob/reconcile-transactions reconcile-manual -n klinematrix-test
```

### Troubleshooting

**CronJob not running:**
```bash
# Check CronJob definition
kubectl describe cronjob reconcile-transactions -n klinematrix-test

# Check if suspended
kubectl get cronjob reconcile-transactions -n klinematrix-test -o jsonpath='{.spec.suspend}'
# Should be: false or <empty>

# Check recent events
kubectl get events -n klinematrix-test --sort-by='.lastTimestamp' | grep reconcile
```

**Job failing:**
```bash
# Get failed job name
kubectl get jobs -n klinematrix-test -l app=reconcile-transactions | grep -E '0/1|Failed'

# View logs
kubectl logs job/<job-name> -n klinematrix-test

# Common issues:
# 1. MongoDB connection - check External Secrets sync
# 2. Image pull - verify ACR credentials
# 3. Python import errors - rebuild backend image
```

**No stuck transactions found:**
```bash
# This is normal! It means:
# 1. All transactions are completing successfully
# 2. No crashes during credit deduction
# 3. System is healthy

# To test reconciliation:
# 1. Create a PENDING transaction manually in MongoDB
# 2. Wait for next CronJob run
# 3. Check if it gets completed/failed
```

---

## Adjust CronJob Schedule

**Every 5 minutes** (more aggressive):
```yaml
spec:
  schedule: "*/5 * * * *"
```

**Every hour** (less aggressive):
```yaml
spec:
  schedule: "0 * * * *"
```

**Twice per day** (minimal overhead):
```yaml
spec:
  schedule: "0 2,14 * * *"  # 2 AM and 2 PM
```

Apply changes:
```bash
kubectl apply -k .pipeline/k8s/overlays/test
```

---

## Verification Checklist

### Backend
- [x] Transaction indexes created on startup
- [x] Credit endpoints registered (`/api/users/me`, `/api/credits/transactions`)
- [x] Chat endpoint integrated with credit system
- [x] Health endpoint shows MongoDB + Redis connected

### Reconciliation Worker
- [x] Runs successfully in docker-compose
- [x] Connects to MongoDB
- [x] Finds and processes stuck transactions
- [x] Logs clear success/failure messages

### Kubernetes
- [x] CronJob created in namespace
- [x] Schedule configured (default: every 10 minutes)
- [x] Jobs run on schedule
- [x] Logs show successful reconciliation

### Frontend
- [x] TypeScript types defined (`credits.ts`)
- [x] API client methods added (`creditService`)
- [x] React Query hooks created (`useCredits.ts`)
- [x] Components built (`CreditBalance.tsx`, `TransactionHistory.tsx`)

---

## Monitoring

### Key Metrics
- **Reconciliation rate**: How many transactions reconciled per run
- **Failure rate**: How many transactions failed reconciliation
- **Job duration**: Time taken per reconciliation run

### Logs to Watch
```bash
# Backend startup
docker-compose logs backend | grep "Transaction indexes created"

# Credit deduction
docker-compose logs backend | grep "Credits checked and transaction created"

# Reconciliation runs
docker-compose logs backend | grep "Reconciliation worker finished"
```

### MongoDB Queries
```javascript
// Count transactions by status
db.transactions.aggregate([
  { $group: { _id: "$status", count: { $sum: 1 } } }
])

// Find old PENDING transactions (>10 minutes)
db.transactions.find({
  status: "PENDING",
  created_at: { $lt: new Date(Date.now() - 10*60*1000) }
})

// User with most credits spent
db.users.find().sort({ total_credits_spent: -1 }).limit(5)
```

---

## Cost Optimization

**CronJob Resource Limits:**
- Memory: 128Mi request, 256Mi limit
- CPU: 50m request, 200m limit

**Why lightweight?**
- Short-lived job (runs for ~1-2 seconds)
- Only queries MongoDB, no heavy computation
- Exits immediately after reconciliation

**Cost estimate:**
- ~1 second per run
- 144 runs per day (every 10 mins)
- ~2.4 minutes of compute per day
- Negligible cost compared to main backend deployment
