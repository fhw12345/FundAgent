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
    content: `# 🎯 Welcome to Financial Agent!

---

### ✨ **First Time Here?**

Click the **❓** button in the bottom-right corner for a quick interactive guide!

---

### 🚀 **Three Powerful Modes to Explore:**

🤖 **Agent Mode** — Let AI automatically analyze and provide insights

💬 **Copilot Mode** — You control, AI guides

📊 **Portfolio Tracking** — Monitor your investment performance

---

> 💡 **Pro Tip:** Start by asking a question or searching for a stock symbol to see the magic happen!`,
    timestamp: new Date().toISOString(),
  },
];

export const useChatManager = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [chatId, setChatId] = useState<string | null>(null);

  return { messages, setMessages, chatId, setChatId };
};
