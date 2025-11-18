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
│  │ 1. LLM Reasoning → 2. Tool Decision → 3. Execute │           │
│  │ 4. Observe Result → 5. More tools OR Final Answer│           │
│  └──────────────────────────────────────────────────┘           │
│                                                                   │
│  Checkpointer (MemorySaver): Stores state by thread_id          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Financial Analysis Tools                      │
│                                                                   │
│  1. fibonacci_analysis_tool → Compresses to 2-3 lines           │
│  2. stochastic_analysis_tool → Compresses to 2-3 lines          │
│  3. fundamentals_tool → Returns compressed fundamentals          │
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
  onChunk, onChatCreated, onTitleGenerated, onDone, onError,
  { agent_version: "v3", model: "qwen-plus" }
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
                chat_id=chat_id, user_id=user_id,
                role="user", content=request.message, source="user",
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

            # STEP 5-8: Stream response, save to MongoDB, send completion
            final_answer = result["final_answer"]
            for char in final_answer:
                yield f"data: {json.dumps({'type': 'chunk', 'content': char})}\n\n"
                await asyncio.sleep(0.01)

            await chat_service.add_message(
                chat_id=chat_id, user_id=user_id,
                role="assistant", content=final_answer, source="agent",
            )
            yield f"data: {json.dumps({'type': 'done', 'chat_id': chat_id})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

**Key Points**:
- ✅ Manages MongoDB persistence
- ✅ Gets conversation history for context
- ✅ Delegates AI work to agent.ainvoke()
- ✅ Streams response back to frontend

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
    Agent autonomously: reasons → decides tools → executes → synthesizes
    """

    trace_id = f"trace_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    thread_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Prepare messages
    messages = []
    if conversation_history:
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # Run ReAct loop ◄── LangGraph SDK handles everything
        result = await self.agent.ainvoke({"messages": messages}, config=config)

        # Extract final answer
        final_message = result["messages"][-1]
        final_answer = final_message.content if hasattr(final_message, "content") else ""

        # Count tool executions
        tool_messages = [
            msg for msg in result["messages"]
            if msg.__class__.__name__ == "ToolMessage"
        ]

        return {
            "trace_id": trace_id,
            "messages": result["messages"],
            "final_answer": final_answer,
            "tool_executions": len(tool_messages),
        }

    except Exception as e:
        logger.error("ReAct agent invocation failed", trace_id=trace_id, error=str(e))
        return {
            "trace_id": trace_id, "messages": [],
            "final_answer": f"Error: {str(e)}", "tool_executions": 0,
        }
```

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

**Example: "Analyze AAPL with Fibonacci and check momentum"**

```
┌─────────────────────────────────────────────────────────┐
│ ITERATION 1: LLM Reasoning                              │
│ LLM thinks: "User wants Fibonacci analysis for AAPL."   │
│ Decision: CALL TOOL - fibonacci_analysis_tool           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ TOOL EXECUTION 1: Fibonacci Analysis                    │
│ Returns: "Fibonacci: AAPL @ $180.50                    │
│ Key Levels: 38.2% ($175.20), 61.8% ($172.10)           │
│ Trend Strength: Strong Uptrend, Confidence: 87%"       │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ ITERATION 2: LLM Observes Result                        │
│ LLM thinks: "Need momentum check too."                  │
│ Decision: CALL ANOTHER TOOL - stochastic_analysis_tool │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ TOOL EXECUTION 2: Stochastic Analysis                   │
│ Returns: "Stochastic: %K=72.5, %D=68.3                 │
│ Signal: Bullish Crossover, Momentum: Strong"           │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│ ITERATION 3: LLM Synthesizes Final Answer               │
│ LLM sees both results, generates comprehensive response │
│ Decision: FINAL ANSWER                                  │
└─────────────────────────────────────────────────────────┘
                          │
                          ▼
                    LOOP ENDS
            Return final answer to ainvoke()
```

---

## Related Documentation

- [Components, Patterns & Debugging](react-agent-debugging.md) - Detailed component explanations, design patterns, performance metrics, and debugging tips
- [SDK ReAct Agent Feature Spec](../features/langgraph-sdk-react-agent.md) - Feature specification and requirements
- [Agent Architecture](agent-architecture.md) - 12-Factor agent implementation details
