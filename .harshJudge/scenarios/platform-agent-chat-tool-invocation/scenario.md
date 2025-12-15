---
id: platform-agent-chat-tool-invocation
title: Platform Agent Chat Tool Invocation E2E Test
tags: [platform, agent, chat, tools, llm, e2e]
estimatedDuration: 90
---

# Platform Agent Chat Tool Invocation E2E Test

## Objective
Verify that the Platform chat in Agent mode:
1. Accepts user questions about stocks
2. Invokes appropriate tools (e.g., get_stock_quote, get_company_overview, get_news_sentiment)
3. Returns LLM responses that are relevant to the tool context and user question

## Preconditions
- Local environment running (docker-compose)
- User account exists (allenpan/admin123)
- Backend API is healthy

## Test Steps

### Step 1: Navigate to Platform and Verify Agent Mode
1. Navigate to http://localhost:3000
2. Login if not already logged in (allenpan/admin123)
3. Click on "平台" (Platform) navigation button
4. Verify Agent mode is selected (🤖 代理 button should be active)
5. **Evidence**: Screenshot showing Platform page with Agent mode selected

### Step 2: Send a Stock Analysis Question
1. Type a question about a stock in the chat input, e.g., "What is the current price and recent news for AAPL?"
2. Press Enter or click Send button
3. Wait for the response to complete
4. **Evidence**: Screenshot showing the question sent

### Step 3: Verify Tool Invocation
1. Observe the chat response area
2. Look for tool execution indicators (tool cards, loading spinners)
3. Verify at least one tool was invoked (e.g., get_stock_quote, get_news_sentiment)
4. **Evidence**: Screenshot showing tool invocation in progress or completed

### Step 4: Verify LLM Response Relevance
1. Wait for the complete LLM response
2. Verify the response contains:
   - Stock price information (if price tool was used)
   - News sentiment or headlines (if news tool was used)
   - Relevant analysis based on the tools' output
3. Verify the response is contextually relevant to the original question
4. **Evidence**: Screenshot of the complete response with tool results

### Step 5: Verify Response Quality
1. Check that the response is in the user's language (Chinese based on locale)
2. Verify no error messages in the response
3. Check backend logs for successful tool execution
4. **Evidence**: Screenshot or log capture confirming successful flow

## Expected Results
- ✅ Agent mode is active and accepts questions
- ✅ At least one tool is invoked based on the question
- ✅ Tool results are displayed or incorporated into the response
- ✅ LLM response is relevant to both the question and tool context
- ✅ No errors in the chat flow

## Failure Criteria
- ❌ Agent mode not available or not working
- ❌ No tools invoked for a stock-related question
- ❌ LLM response is generic and doesn't use tool context
- ❌ Error messages or failed tool executions
- ❌ Response timeout or incomplete response
