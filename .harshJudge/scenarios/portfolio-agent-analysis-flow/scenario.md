---
id: portfolio-agent-analysis-flow
title: Portfolio Agent Analysis Complete Flow E2E Test
tags: [portfolio, agent, analysis, orders, decisions, e2e]
estimatedDuration: 120
---

# Portfolio Agent Analysis Complete Flow E2E Test

## Objective
Verify that the Portfolio Agent Analysis flow works end-to-end:
1. Individual symbol analyses are generated and stored
2. Portfolio-level decisions are generated based on analyses
3. Orders are placed based on portfolio decisions
4. All data is consistent and visible in the UI

## Preconditions
- Local environment running (docker-compose)
- User account exists (allenpan/admin123)
- Portfolio has holdings and/or watchlist items

## Test Steps

### Step 1: Login and Navigate to Portfolio Dashboard
1. Navigate to http://localhost:3000
2. Login with credentials: allenpan / admin123
3. Navigate to Portfolio Dashboard
4. **Evidence**: Screenshot of Portfolio Dashboard loaded

### Step 2: Trigger Portfolio Analysis (Admin)
1. Look for the CronController or admin trigger button
2. Click "Analyze Now" or equivalent trigger
3. Wait for analysis to complete (check backend logs)
4. **Evidence**: Screenshot showing analysis triggered

### Step 3: Verify Individual Symbol Analyses
1. In the Portfolio sidebar, check chat history
2. Filter by "Individual" analysis type
3. Verify each holding/watchlist symbol has an analysis entry
4. Click on one analysis to view details
5. **Evidence**: Screenshot of individual analysis list and detail view

### Step 4: Verify Portfolio Decisions
1. Filter by "Portfolio Decisions" analysis type
2. Verify a portfolio decision entry exists
3. Click to view the decision summary
4. Verify it contains BUY/SELL/HOLD decisions for multiple symbols
5. **Evidence**: Screenshot of portfolio decisions view

### Step 5: Verify Orders Placed
1. Navigate to the Orders section or Transaction History
2. Verify orders match the portfolio decisions
3. Check order details (symbol, side, quantity)
4. **Evidence**: Screenshot of orders list

### Step 6: Verify Data Consistency
1. Cross-check: Symbols in individual analyses match portfolio decisions
2. Cross-check: Order symbols match SELL/BUY decisions (not HOLD)
3. Verify timestamps are consistent (analyses before decisions before orders)
4. **Evidence**: Summary screenshot or console verification

## Expected Results
- ✅ Individual analyses exist for each portfolio symbol
- ✅ Portfolio decisions document exists with multi-symbol assessment
- ✅ Orders placed match the BUY/SELL decisions
- ✅ Timeline is logical: individual → portfolio → orders

## Failure Criteria
- ❌ No individual analyses found
- ❌ No portfolio decisions generated
- ❌ Orders don't match decisions
- ❌ Missing symbols in analysis chain
