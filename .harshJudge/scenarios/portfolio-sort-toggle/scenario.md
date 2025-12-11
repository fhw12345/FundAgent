---
id: portfolio-sort-toggle
title: Portfolio Chat Sort Toggle E2E Test
tags: [portfolio, sort, ui]
estimatedDuration: 60
---

# Portfolio Chat Sort Toggle Test

## Objective
Verify the sort toggle in Portfolio Chat Sidebar switches between "Newest First" and "Oldest First".

## Steps

### Step 1: Login
- Navigate to http://localhost:3000
- Login with allenpan/admin123

### Step 2: Navigate to Portfolio
- Click Portfolio in navigation
- Verify Analysis History sidebar is visible

### Step 3: Verify Sort Toggle
- Find sort toggle button with "Sort by:" label
- Default should show "Newest First"

### Step 4: Toggle Sort Order
- Click sort toggle button
- Verify it changes to "Oldest First"

### Step 5: Toggle Back
- Click sort toggle again
- Verify it returns to "Newest First"
