---
id: message-sort-toggle-ux
title: Message Sort Toggle New UX Test
tags: [portfolio, sort, messages, ux, toggle]
estimatedDuration: 120
---

# Message Sort Toggle New UX Test

Tests the updated message sort toggle UX in Portfolio Dashboard:
- Text-based toggle (not button with icon)
- Highlighted (blue) when ON (newest first)
- Gray when OFF (oldest first)
- Only affects messages within chat modal, not chat list order

## Prerequisites
- Local dev environment running (localhost:3000)
- User logged in as allenpan
- At least one analysis chat exists with multiple messages

## Steps

### Step 1: Navigate to Portfolio Dashboard
1. Navigate to http://localhost:3000/portfolio
2. Verify portfolio dashboard loads
3. Screenshot: Initial page state

### Step 2: Verify Chat Sidebar Shows Toggle
1. Expand chat sidebar if collapsed
2. Look for "消息排序: 最新在前" or "Messages: Latest on top" text
3. Verify the toggle text is highlighted (blue color) by default
4. Screenshot: Sidebar with toggle visible

### Step 3: Open a Chat with Messages
1. Click on an analysis chat item (e.g., "AAPL Analysis")
2. Verify chat modal opens
3. Note the order of messages (should be newest first)
4. Screenshot: Chat modal with messages

### Step 4: Toggle to Oldest First
1. Click the "最新在前" / "Latest on top" toggle text
2. Verify toggle text becomes gray (not highlighted)
3. Open the same chat again
4. Verify messages are now in oldest-first order
5. Screenshot: Messages in oldest-first order

### Step 5: Toggle Back to Newest First
1. Click the toggle text again
2. Verify toggle text becomes blue (highlighted)
3. Open chat and verify newest messages appear first
4. Screenshot: Messages back to newest-first order
