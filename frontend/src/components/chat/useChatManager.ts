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
    content: `## Welcome to Financial Agent 👋

**Get Started:** Search for a stock symbol on the right (e.g., "AAPL" or "Apple") to begin your analysis.

> *Professional trading interface with AI-powered insights, interactive charts, and real-time data.*`,
    timestamp: new Date().toISOString(),
  },
];

export const useChatManager = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [sessionId, setSessionId] = useState<string | null>(null);

  return { messages, setMessages, sessionId, setSessionId };
};
