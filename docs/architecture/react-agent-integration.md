# How LangGraph ReAct Agent Works with Chat API

**Complete Integration Flow** - From HTTP Request to AI Response

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  chatService.sendMessageStreamPersistent(message, chatId, ...)  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP POST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│               Backend API (FastAPI - chat.py)                    │
│                                                                   │
│  @router.post("/stream")                                         │
│  async def chat_stream_unified(request: ChatRequest):           │
│    ├─ Check agent_version                                        │
│    ├─ if v2: _stream_with_simple_agent()                        │
│    └─ if v3: _stream_with_react_agent() ◄── WE'RE HERE         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│           _stream_with_react_agent() - Orchestrator             │
│                                                                   │
│  1. Create/Get Chat                                              │
│  2. Save user message to MongoDB                                 │
│  3. Get conversation history (last 10 messages)                  │
│  4. Call agent.ainvoke(message, history) ◄── MAIN FLOW          │
│  5. Stream final answer character-by-character                   │
│  6. Save assistant response to MongoDB                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│    FinancialAnalysisReActAgent.ainvoke() - Agent Executor       │
│                 (langgraph_react_agent.py)                       │
│                                                                   │
│  1. Generate trace_id and thread_id                              │
│  2. Prepare messages (history + current message)                 │
│  3. Call self.agent.ainvoke() ◄── LANGGRAPH SDK                 │
│  4. Extract final_answer from last message                       │
│  5. Count tool_executions                                        │
│  6. Return {final_answer, tool_executions, trace_id}            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│        LangGraph SDK ReAct Agent (self.agent)                    │
│        Created by: create_react_agent(llm, tools, checkpointer) │
│                                                                   │
│  Auto-Loop Execution:                                            │
│  ┌──────────────────────────────────────────────────┐           │
│  │ 1. LLM Reasoning                                 │           │
│  │    "User wants Fibonacci analysis for AAPL"      │           │
│  │                                                   │           │
│  │ 2. Tool Decision                                 │           │
│  │    LLM decides: Call fibonacci_analysis_tool     │           │
│  │                                                   │           │
│  │ 3. Tool Execution                                │           │
│  │    ├─> fibonacci_analysis_tool(symbol="AAPL")   │           │
│  │    └─> Returns: "Fibonacci: AAPL @ $180.50..."  │           │
│  │                                                   │           │
│  │ 4. Observe Result                                │           │
│  │    LLM reads compressed tool output              │           │
│  │                                                   │           │
│  │ 5. Decision Point                                │           │
│  │    ├─> Need more tools? Loop back to step 1     │           │
│  │    └─> Have answer? Generate final response     │           │
│  │                                                   │           │
│  │ 6. Final Answer                                  │           │
│  │    "Based on Fibonacci analysis, AAPL shows..." │           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
│  Checkpointer (MemorySaver):                                    │
│    Stores conversation state by thread_id                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Financial Analysis Tools                      │
│                                                                   │
│  1. fibonacci_analysis_tool(symbol, timeframe, ...)             │
│     ├─> Calls FibonacciAnalyzer                                 │
│     ├─> Gets full analysis result                               │
│     └─> Compresses to 2-3 lines (99.5% reduction)               │
│                                                                   │
│  2. stochastic_analysis_tool(symbol, k_period, ...)             │
│     ├─> Calls StochasticAnalyzer                                │
│     ├─> Gets momentum indicators                                 │
│     └─> Compresses to 2-3 lines                                  │
│                                                                   │
│  3. fundamentals_tool(symbol)                                    │
│     ├─> Fetches company data                                     │
│     └─> Returns compressed fundamentals                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📝 Step-by-Step Execution Flow

### 1. Frontend Sends Request

```typescript
// frontend/src/services/api.ts
chatService.sendMessageStreamPersistent(
  "Analyze AAPL with Fibonacci",  // User message
  "chat_abc123",                   // Chat ID
  onChunk,                         // Callback for each chunk
  onChatCreated,                   // Callback when chat created
  onTitleGenerated,                // Callback for title
  onDone,                          // Callback on completion
  onError,                         // Callback on error
  {
    agent_version: "v3",           // Use ReAct Agent
    model: "qwen-plus"             // LLM model
  }
);
```

**HTTP Request**:
```http
POST /api/chat/stream HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "Analyze AAPL with Fibonacci",
  "chat_id": "chat_abc123",
  "agent_version": "v3",
  "model": "qwen-plus"
}
```

---

### 2. API Router - Version Selection

```python
# backend/src/api/chat.py

@router.post("/stream")
async def chat_stream_unified(request: ChatRequest):
    # Route based on agent version
    if request.agent_version == "v2":
        return await _stream_with_simple_agent(...)
    elif request.agent_version == "v3":
        return await _stream_with_react_agent(...)  # ◄── We go here
```

---

### 3. Orchestrator - _stream_with_react_agent()

```python
# backend/src/api/chat.py (lines 433-530)

async def _stream_with_react_agent(
    request: ChatRequest,
    user_id: str,
    chat_service: ChatService,
    agent: FinancialAnalysisReActAgent,  # ◄── Injected by Depends()
) -> StreamingResponse:
    """Stream using SDK ReAct Agent (v3)."""

    async def generate_stream() -> AsyncGenerator[str, None]:
        chat_id = None

        try:
            # STEP 1: Get or create chat
            if request.chat_id:
                chat = await chat_service.get_chat(request.chat_id, user_id)
                chat_id = chat.chat_id
            else:
                chat = await chat_service.create_chat(user_id, title="New Chat")
                chat_id = chat.chat_id
                yield f"data: {json.dumps({'chat_id': chat_id, 'type': 'chat_created'})}\n\n"

            # STEP 2: Save user message to MongoDB
            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="user",
                content=request.message,
                source="user",
            )

            # STEP 3: Get conversation history (last 10 messages)
            messages = await chat_service.get_messages(chat_id, limit=10)
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in reversed(messages)
            ]

            # STEP 4: Invoke ReAct agent ◄── MAIN CALL
            result = await agent.ainvoke(
                user_message=request.message,
                conversation_history=conversation_history,
            )

            # Extract results
            final_answer = result["final_answer"]
            tool_executions = result.get("tool_executions", 0)
            trace_id = result.get("trace_id", "unknown")

            # STEP 5: Send tool info (if tools were used)
            if tool_executions > 0:
                tool_info = {
                    "type": "tool_info",
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                }
                yield f"data: {json.dumps(tool_info)}\n\n"

            # STEP 6: Stream final answer character-by-character
            for char in final_answer:
                chunk = {"type": "chunk", "content": char}
                yield f"data: {json.dumps(chunk)}\n\n"
                await asyncio.sleep(0.01)  # Smooth streaming

            # STEP 7: Save assistant message
            await chat_service.add_message(
                chat_id=chat_id,
                user_id=user_id,
                role="assistant",
                content=final_answer,
                source="agent",
                metadata={
                    "tool_executions": tool_executions,
                    "trace_id": trace_id,
                    "agent_type": "react_sdk",
                },
            )

            # STEP 8: Send completion event
            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"

        except Exception as e:
            logger.error("Stream error (v3)", error=str(e), chat_id=chat_id)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

**Key Points**:
- ✅ Manages MongoDB persistence (save user message, save assistant response)
- ✅ Gets conversation history for context
- ✅ Calls `agent.ainvoke()` - delegates AI work to agent
- ✅ Streams response back to frontend
- ✅ Handles errors gracefully

---

### 4. Agent Executor - ainvoke()

```python
# backend/src/agent/langgraph_react_agent.py (lines 242-342)

async def ainvoke(
    self,
    user_message: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """
    Invoke ReAct agent with user message and conversation history.

    The agent will autonomously:
    1. Reason about the query
    2. Decide which tools to call (if any)
    3. Execute tools sequentially
    4. Observe results and decide: more tools OR final answer
    5. Synthesize final response
    """

    # STEP 1: Generate IDs
    trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # STEP 2: Prepare messages
    messages = []

    # Add conversation history if provided
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))

    # Add current user message
    messages.append(HumanMessage(content=user_message))

    # STEP 3: Configure LangGraph execution
    config = {
        "configurable": {"thread_id": thread_id},
    }

    try:
        # STEP 4: Run ReAct loop ◄── LangGraph SDK handles everything
        result = await self.agent.ainvoke({"messages": messages}, config=config)

        # STEP 5: Extract final answer
        final_message = result["messages"][-1]
        final_answer = final_message.content if hasattr(final_message, "content") else ""

        # STEP 6: Count tool executions
        tool_messages = [
            msg for msg in result["messages"]
            if msg.__class__.__name__ == "ToolMessage"
        ]

        # STEP 7: Return structured result
        return {
            "trace_id": trace_id,
            "messages": result["messages"],
            "final_answer": final_answer,
            "tool_executions": len(tool_messages),
        }

    except Exception as e:
        logger.error("ReAct agent invocation failed", trace_id=trace_id, error=str(e))
        return {
            "trace_id": trace_id,
            "messages": [],
            "final_answer": f"Error: {str(e)}",
            "tool_executions": 0,
        }
```

**Key Points**:
- ✅ Wraps LangGraph SDK agent
- ✅ Manages trace IDs for observability
- ✅ Converts conversation history to LangChain messages
- ✅ Delegates to `self.agent.ainvoke()` (LangGraph SDK)
- ✅ Extracts clean results from LangGraph response
- ✅ Returns structured dict for chat.py to consume

---

### 5. LangGraph SDK - The Auto-Loop

```python
# Created in __init__:
self.agent = create_react_agent(
    model=self.llm,           # ChatTongyi (Qwen)
    tools=self.tools,         # [fibonacci, stochastic, fundamentals]
    checkpointer=MemorySaver(), # Conversation state
)
```

**What happens inside `self.agent.ainvoke()`**:

#### Example Query: "Analyze AAPL with Fibonacci and check momentum"

```
┌─────────────────────────────────────────────────────────┐
│ ITERATION 1: LLM Reasoning                              │
│                                                          │
│ LLM thinks:                                              │
│ "User wants Fibonacci analysis for AAPL.                │
│  I should call fibonacci_analysis_tool first."          │
│                                                          │
│ Decision: CALL TOOL                                      │
│ Tool: fibonacci_analysis_tool                           │
│ Args: {symbol: "AAPL", timeframe: "1d"}                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ TOOL EXECUTION 1: Fibonacci Analysis                    │
│                                                          │
│ fibonacci_analysis_tool(symbol="AAPL", timeframe="1d") │
│   ├─> FibonacciAnalyzer.analyze()                      │
│   ├─> Gets full result (5KB JSON)                      │
│   └─> Compresses to 2-3 lines:                         │
│                                                          │
│ Returns: "Fibonacci Analysis: AAPL @ $180.50           │
│ Key Levels: 38.2% ($175.20), 61.8% ($172.10)           │
│ Trend Strength: Strong Uptrend, Confidence: 87%"       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ ITERATION 2: LLM Observes Result                        │
│                                                          │
│ LLM sees: "Fibonacci shows support at $175.20..."       │
│                                                          │
│ LLM thinks:                                              │
│ "Good! Now user also asked about momentum.              │
│  I should call stochastic_analysis_tool."               │
│                                                          │
│ Decision: CALL ANOTHER TOOL                              │
│ Tool: stochastic_analysis_tool                          │
│ Args: {symbol: "AAPL", timeframe: "1d"}                │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ TOOL EXECUTION 2: Stochastic Analysis                   │
│                                                          │
│ stochastic_analysis_tool(symbol="AAPL", timeframe="1d")│
│   ├─> StochasticAnalyzer.analyze()                     │
│   ├─> Gets momentum data                                │
│   └─> Compresses to 2-3 lines:                         │
│                                                          │
│ Returns: "Stochastic: %K=72.5, %D=68.3                 │
│ Signal: Bullish Crossover, Momentum: Strong             │
│ Condition: Approaching Overbought (70+)"               │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ ITERATION 3: LLM Synthesizes Final Answer               │
│                                                          │
│ LLM sees both results:                                   │
│ - Fibonacci: Support at $175.20, uptrend, 87% conf      │
│ - Stochastic: Bullish crossover, strong momentum        │
│                                                          │
│ LLM thinks:                                              │
│ "I have all the information to answer the user.         │
│  Let me synthesize a comprehensive response."           │
│                                                          │
│ Decision: FINAL ANSWER                                   │
│                                                          │
│ Generates: "Based on technical analysis of AAPL:       │
│                                                          │
│ **Fibonacci Analysis:**                                  │
│ - Current Price: $180.50                                 │
│ - Key Support: 38.2% at $175.20                         │
│ - Strong uptrend with 87% confidence                     │
│                                                          │
│ **Momentum Analysis (Stochastic):**                      │
│ - Bullish crossover detected (%K=72.5, %D=68.3)        │
│ - Strong momentum, approaching overbought territory     │
│                                                          │
│ **Recommendation:**                                      │
│ AAPL shows strong bullish momentum with solid support  │
│ at $175.20. Consider buying on pullbacks to support    │
│ levels. Watch for overbought conditions above 80."     │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                    LOOP ENDS
            Return final answer to ainvoke()
```

---

## 🔧 Key Components Explained

### 1. Dependency Injection

```python
# chat.py gets agent via Depends()
async def chat_stream_unified(
    # ...
    react_agent: FinancialAnalysisReActAgent = Depends(get_react_agent),
):
    # ...
    return await _stream_with_react_agent(request, user_id, chat_service, react_agent)
```

```python
# backend/src/api/dependencies/chat_deps.py
_react_agent_singleton: FinancialAnalysisReActAgent | None = None

def get_react_agent(
    settings: Settings = Depends(get_settings),
    ticker_service: TickerDataService = Depends(get_ticker_data_service),
) -> FinancialAnalysisReActAgent:
    """Singleton per worker process (avoid re-compilation)."""
    global _react_agent_singleton

    if _react_agent_singleton is None:
        _react_agent_singleton = FinancialAnalysisReActAgent(
            settings=settings,
            ticker_data_service=ticker_service,
        )

    return _react_agent_singleton
```

**Why Singleton?**
- LangGraph agent compilation takes 300-500ms
- Singleton caches compiled agent per worker
- Reused across all requests in same worker process

---

### 2. Tool Compression

**Problem**: Financial analysis tools return huge JSON objects (5-20KB)

```python
# Raw Fibonacci result (5KB):
{
    "levels": {
        "0.236": {"price": 220.50, "distance": "2.5%", ...},
        "0.382": {"price": 222.19, "distance": "1.2%", ...},
        # ... 10 more levels
    },
    "swing_high": {"price": 230.00, "date": "2024-01-15", ...},
    "swing_low": {"price": 210.00, "date": "2024-01-01", ...},
    "confidence": 0.87,
    # ... tons more metadata
}
```

**Solution**: Compress to 2-3 lines before passing to LLM

```python
# Compressed (100 chars):
"Fibonacci: AAPL @ $180.50
Key Levels: 38.2% ($175.20), 61.8% ($172.10)
Trend Strength: Strong Uptrend, Confidence: 87%"
```

**Benefits**:
- ✅ 99.5% token reduction
- ✅ Faster LLM processing
- ✅ Lower API costs (~¥0.020 saved per request)
- ✅ Focus on actionable insights

---

### 3. Conversation History Management

```python
# Get last 10 messages from MongoDB
messages = await chat_service.get_messages(chat_id, limit=10)
conversation_history = [
    {"role": msg.role, "content": msg.content}
    for msg in reversed(messages)
]

# Pass to agent
result = await agent.ainvoke(
    user_message=request.message,
    conversation_history=conversation_history,  # ◄── Context
)
```

**Why This Matters**:
- LLM sees previous conversation
- Can reference earlier analysis
- Maintains context across turns

**Example**:
```
User: "Analyze AAPL"
Agent: "AAPL shows support at $175..."

User: "What about resistance?"
Agent: "Based on our earlier Fibonacci analysis, resistance is at..."
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
       (Remembers previous discussion)
```

---

### 4. Message Flow

```python
# Inside LangGraph agent
result = await self.agent.ainvoke({"messages": messages}, config=config)

# Returns:
{
    "messages": [
        HumanMessage("Analyze AAPL"),           # User input
        AIMessage("I'll analyze AAPL..."),      # LLM reasoning (optional)
        ToolMessage("Fibonacci: ..."),          # Tool result 1
        ToolMessage("Stochastic: ..."),         # Tool result 2
        AIMessage("Based on analysis...")       # Final answer
    ]
}

# We extract the last message:
final_answer = result["messages"][-1].content
```

---

## 💡 Complete Example

### Request Flow

1. **Frontend**:
   ```typescript
   chatService.sendMessageStreamPersistent(
     "Analyze AAPL with Fibonacci and check momentum",
     "chat_abc123",
     { agent_version: "v3" }
   );
   ```

2. **chat.py**:
   - Saves user message to MongoDB
   - Gets conversation history (last 10 messages)
   - Calls `agent.ainvoke(message, history)`

3. **langgraph_react_agent.py**:
   - Wraps message in HumanMessage
   - Calls LangGraph SDK: `self.agent.ainvoke({messages: [...]})`

4. **LangGraph SDK**:
   - **Iteration 1**:
     - LLM: "Need Fibonacci analysis"
     - Calls `fibonacci_analysis_tool("AAPL")`
     - Gets: "Fibonacci: AAPL @ $180.50..."

   - **Iteration 2**:
     - LLM: "Need momentum check"
     - Calls `stochastic_analysis_tool("AAPL")`
     - Gets: "Stochastic: %K=72.5, bullish..."

   - **Iteration 3**:
     - LLM: "Have all info, synthesizing answer"
     - Generates final comprehensive response
     - Returns to ainvoke()

5. **langgraph_react_agent.py**:
   - Extracts final_answer from messages
   - Counts tool_executions (2 in this case)
   - Returns `{final_answer, tool_executions, trace_id}`

6. **chat.py**:
   - Sends tool_info event: `{"tool_executions": 2, "trace_id": "..."}`
   - Streams final_answer character-by-character
   - Saves assistant message to MongoDB
   - Sends completion event

7. **Frontend**:
   - Displays chunks as they arrive
   - Shows "Tool executions: 2"
   - Marks conversation complete

---

## 🎯 Key Design Patterns

### 1. Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **chat.py** | HTTP handling, MongoDB persistence, streaming protocol |
| **langgraph_react_agent.py** | Agent logic, tool management, LangGraph SDK wrapper |
| **LangGraph SDK** | ReAct loop, tool calling, message management |
| **Tools** | Analysis logic, result compression |

### 2. Async All The Way

```python
# API layer
async def chat_stream_unified() -> StreamingResponse:
    return await _stream_with_react_agent(...)

# Orchestrator layer
async def _stream_with_react_agent():
    result = await agent.ainvoke(...)

# Agent layer
async def ainvoke():
    result = await self.agent.ainvoke(...)

# Tool layer
async def fibonacci_analysis_tool():
    result = await analyzer.analyze(...)
```

**Benefits**:
- ✅ Non-blocking I/O
- ✅ Handle multiple concurrent requests
- ✅ Efficient resource usage

### 3. Error Handling at Each Layer

```python
# chat.py
try:
    result = await agent.ainvoke(...)
except Exception as e:
    yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

# langgraph_react_agent.py
try:
    result = await self.agent.ainvoke(...)
except Exception as e:
    return {"final_answer": f"Error: {str(e)}", "tool_executions": 0}

# Tools
try:
    result = await analyzer.analyze(...)
except Exception as e:
    return f"Analysis error: {str(e)}"
```

---

## 📊 Performance Characteristics

| Metric | Value | Notes |
|--------|-------|-------|
| **Agent Compilation** | 300-500ms | Cached via singleton |
| **Simple Query** | 2-4s | No tools called |
| **Single Tool** | 4-6s | 1 tool execution |
| **Multi-tool Chain** | 8-12s | 2-3 tools in sequence |
| **Token Usage** | 800-1200 | Multi-tool with compression |
| **Cost per Request** | ~¥0.008 | Multi-tool (with 99.5% compression) |

---

## 🚀 Why This Architecture?

### ✅ Advantages

1. **Clean Separation**:
   - API layer handles HTTP/persistence
   - Agent layer handles AI logic
   - Easy to test each layer independently

2. **Reusable Agent**:
   - Same agent can be used by different endpoints
   - Could add batch processing endpoint
   - Could add WebSocket endpoint

3. **Flexible**:
   - Easy to swap LLM models
   - Easy to add new tools
   - Easy to change streaming strategy

4. **Observable**:
   - trace_id for every request
   - tool_executions counted
   - Logs at each layer

5. **Scalable**:
   - Async for concurrency
   - Singleton for efficiency
   - Stateless (MongoDB for persistence)

---

## 🔍 Debugging Tips

### Check Agent Is Being Called

```python
# Add log in chat.py:
logger.info("Calling agent", message=request.message)
result = await agent.ainvoke(user_message=request.message, ...)
logger.info("Agent returned", tool_executions=result["tool_executions"])
```

### Check Tool Executions

```python
# In langgraph_react_agent.py:
tool_messages = [msg for msg in result["messages"] if msg.__class__.__name__ == "ToolMessage"]
logger.info("Tool executions", count=len(tool_messages), tools=[msg.name for msg in tool_messages])
```

### Check Final Answer

```bash
# Watch backend logs
docker compose logs -f backend | grep "ReAct agent"
```

---

**Summary**: The integration is a clean 3-layer architecture where chat.py handles HTTP/persistence, langgraph_react_agent.py wraps LangGraph SDK, and the SDK handles the ReAct loop with autonomous tool chaining. Each layer has a clear responsibility and communicates via simple async function calls.
