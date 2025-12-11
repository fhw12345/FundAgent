---
id: analysis-type-filter
title: Analysis Type Filter E2E Test
tags: [portfolio, filter, analysis-type, individual, portfolio-decisions]
estimatedDuration: 120
---

# Analysis Type Filter E2E Test

## Objective
Verify the Analysis Type Filter dropdown works correctly to filter portfolio chat history between "Individual Analysis" and "Portfolio Decisions".

## Preconditions
- User is logged in
- Portfolio Dashboard is accessible
- Chat history exists with individual symbol analyses

## Test Steps

### Step 1: Navigate to Portfolio Dashboard
1. Navigate to http://localhost:3000
2. Login with credentials (allenpan/admin123)
3. Click on Portfolio Dashboard link
4. **Expected**: Portfolio Dashboard loads with Analysis History sidebar

### Step 2: Verify Filter Dropdown Exists
1. Locate the Analysis Type filter dropdown in the sidebar
2. **Expected**: Dropdown is visible with label "Analysis Type"
3. **Expected**: Default value is "All Types"

### Step 3: Test "Individual Analysis" Filter
1. Click the Analysis Type dropdown
2. Select "Individual Analysis" option
3. **Expected**: Only individual symbol chats are displayed (e.g., "AAPL Analysis", "GOOG Analysis")
4. **Expected**: Chat count should be > 0

### Step 4: Test "Portfolio Decisions" Filter  
1. Click the Analysis Type dropdown
2. Select "Portfolio Decisions" option
3. **Expected**: Only portfolio decision chats are displayed (or empty if none exist yet)
4. **Expected**: If empty, shows appropriate message

### Step 5: Test "All Types" Filter (Reset)
1. Click the Analysis Type dropdown
2. Select "All Types" option
3. **Expected**: All chats are displayed again
4. **Expected**: Count matches original unfiltered count

### Step 6: Test Combined Filters
1. Select a specific symbol from Symbol filter (e.g., "AAPL")
2. Select "Individual Analysis" from Analysis Type filter
3. **Expected**: Only AAPL individual analysis is shown
4. **Expected**: Filters work together correctly

## Success Criteria
- Filter dropdown renders correctly with proper labels
- "Individual Analysis" filter shows symbol-specific chats
- "Portfolio Decisions" filter shows portfolio-level decisions (or empty state)
- Filters can be combined with symbol filter
- Filter state persists during session
