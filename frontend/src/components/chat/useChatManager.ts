/**
 * useChatManager Hook
 *
 * This hook manages the state of the chat messages. It provides a way
 * to add new messages to the chat history and initializes the chat
 * with a welcome message.
 */

import { useState } from "react";
import type { ChatMessage } from "../../types/api";

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    role: "assistant",
    content: `Hello! I'm your AI financial analysis assistant with enhanced charting capabilities.

🚀 **New Features:**
• **Smart Symbol Search** - Type "Apple" or "AAPL" to find stocks instantly
• **Interactive Charts** - Click once for start date, click again for end date
• **Real-time Data** - Professional TradingView charts with live price feeds
• **Multiple Timeframes** - 1H, 1D, 1W, 1M views for different analysis perspectives

**Get Started:** Search for a stock symbol above to see its chart and start your analysis!`,
    timestamp: new Date().toISOString(),
  },
];

export const useChatManager = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [sessionId, setSessionId] = useState<string | null>(null);

  return { messages, setMessages, sessionId, setSessionId };
};
