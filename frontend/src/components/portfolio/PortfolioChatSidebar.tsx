/**
 * Portfolio Chat Sidebar Component.
 *
 * Displays portfolio agent's analysis history grouped by symbol.
 * Each symbol has its own chat where all analyses are stored as messages.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

interface Message {
  chat_id: string;
  role: string;
  content: string;
  timestamp: string;
  metadata?: {
    symbol?: string;
    interval?: string;
    trend_direction?: string;
    key_levels?: number[];
    analysis_id?: string;
  };
}

interface SymbolChat {
  chat_id: string;
  symbol: string;
  title: string;
  message_count: number;
  messages: Message[];
  latest_timestamp: string;
}

interface ChatHistoryResponse {
  chats: SymbolChat[];
}

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/**
 * Fetch portfolio agent chat history grouped by analysis_id.
 */
async function fetchPortfolioChatHistory(): Promise<ChatHistoryResponse> {
  const response = await fetch(`${API_BASE_URL}/api/portfolio/chat-history`);

  if (!response.ok) {
    throw new Error(`Failed to fetch chat history: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Portfolio Chat Sidebar Component.
 */
export function PortfolioChatSidebar() {
  const [expandedChats, setExpandedChats] = useState<Set<string>>(new Set());

  const { data, isLoading, error } = useQuery({
    queryKey: ["portfolio-chat-history"],
    queryFn: fetchPortfolioChatHistory,
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const toggleChat = (chatId: string) => {
    const newExpanded = new Set(expandedChats);
    if (newExpanded.has(chatId)) {
      newExpanded.delete(chatId);
    } else {
      newExpanded.add(chatId);
    }
    setExpandedChats(newExpanded);
  };

  if (isLoading) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 p-4">
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-500">Loading chat history...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 p-4">
        <div className="flex items-center justify-center h-full">
          <div className="text-red-500">Failed to load chat history</div>
        </div>
      </div>
    );
  }

  const chats = data?.chats || [];

  if (chats.length === 0) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Analysis History</h3>
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-500 text-center">
            <p>No analysis history yet.</p>
            <p className="text-sm mt-2">Add symbols to your watchlist and trigger analysis.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-50 border-l border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">Analysis History</h3>
        <p className="text-sm text-gray-500 mt-1">{chats.length} symbols tracked</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chats.map((chat) => {
          const isExpanded = expandedChats.has(chat.chat_id);
          const symbol = chat.symbol;
          const latestTimestamp = chat.latest_timestamp
            ? new Date(chat.latest_timestamp).toLocaleString()
            : "Unknown time";
          const firstMessage = chat.messages[0];
          const trend = firstMessage?.metadata?.trend_direction;

          return (
            <div
              key={chat.chat_id}
              className="bg-white rounded-lg border border-gray-200 overflow-hidden"
            >
              {/* Chat Header */}
              <button
                onClick={() => toggleChat(chat.chat_id)}
                className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors"
              >
                <div className="flex-1 text-left">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">{symbol}</span>
                    {trend && (
                      <span
                        className={`px-2 py-0.5 text-xs rounded ${
                          trend === "UPTREND"
                            ? "bg-green-100 text-green-800"
                            : trend === "DOWNTREND"
                            ? "bg-red-100 text-red-800"
                            : "bg-gray-100 text-gray-800"
                        }`}
                      >
                        {trend}
                      </span>
                    )}
                    <span className="px-2 py-0.5 text-xs rounded bg-blue-100 text-blue-800">
                      {chat.message_count} analyses
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">Last updated: {latestTimestamp}</div>
                </div>
                <svg
                  className={`w-5 h-5 text-gray-400 transition-transform ${
                    isExpanded ? "transform rotate-180" : ""
                  }`}
                  fill="none"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path d="M19 9l-7 7-7-7"></path>
                </svg>
              </button>

              {/* Expanded Messages */}
              {isExpanded && (
                <div className="border-t border-gray-200 bg-gray-50">
                  {chat.messages.map((message, index) => (
                    <div
                      key={`${message.timestamp}-${index}`}
                      className="px-4 py-3 border-b border-gray-100 last:border-b-0"
                    >
                      <div className="flex items-start gap-3">
                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center">
                          <svg
                            className="w-4 h-4 text-blue-600"
                            fill="none"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                          </svg>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-gray-900 whitespace-pre-wrap break-words">
                            {message.content}
                          </div>
                          {message.metadata?.key_levels && message.metadata.key_levels.length > 0 && (
                            <div className="mt-2 text-xs text-gray-500">
                              <span className="font-medium">Key Levels: </span>
                              {message.metadata.key_levels
                                .map((level) => `$${level.toFixed(2)}`)
                                .join(", ")}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
