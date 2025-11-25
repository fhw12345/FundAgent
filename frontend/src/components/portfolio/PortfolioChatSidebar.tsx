/**
 * Portfolio Chat Sidebar Component.
 *
 * Displays portfolio agent's analysis history grouped by symbol.
 * Each symbol has its own chat where all analyses are stored as messages.
 */

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { SymbolFilter } from "./SymbolFilter";
import { DateRangePicker } from "./DateRangePicker";
import { apiClient } from "../../services/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import type { ChatMessage } from "../../types/api";

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

/**
 * Fetch portfolio agent chat history with optional filters.
 *
 * Uses apiClient (axios) for automatic auth token injection.
 *
 * @param symbol - Filter by symbol (empty for all)
 * @param startDate - Filter from this date (YYYY-MM-DD format)
 * @param endDate - Filter to this date (YYYY-MM-DD format)
 */
async function fetchPortfolioChatHistory(
  symbol?: string,
  startDate?: string,
  endDate?: string
): Promise<ChatHistoryResponse> {
  const params: Record<string, string> = {};

  if (symbol) {
    params.symbol = symbol;
  }
  if (startDate) {
    params.start_date = startDate;
  }
  if (endDate) {
    params.end_date = endDate;
  }

  const response = await apiClient.get<ChatHistoryResponse>(
    "/api/portfolio/chat-history",
    { params }
  );

  return response.data;
}

/**
 * Portfolio Chat Sidebar Component.
 */
export function PortfolioChatSidebar() {
  const { t } = useTranslation(['portfolio', 'common']);
  const [expandedChats, setExpandedChats] = useState<Set<string>>(new Set());

  // Filter state
  const [selectedSymbol, setSelectedSymbol] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  // Fetch chat history with filters
  const { data, isLoading, error } = useQuery({
    queryKey: ["portfolio-chat-history", selectedSymbol, startDate, endDate],
    queryFn: () => fetchPortfolioChatHistory(selectedSymbol, startDate, endDate),
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  // Extract available symbols from all chats (for filter dropdown)
  const availableSymbols = useMemo(() => {
    if (!data?.chats) return [];
    const symbols = data.chats.map((chat) => chat.symbol);
    return Array.from(new Set(symbols)).sort();
  }, [data]);

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
          <div className="text-gray-500">{t('portfolio:chatSidebar.loading')}</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 p-4">
        <div className="flex items-center justify-center h-full">
          <div className="text-red-500">{t('portfolio:chatSidebar.loadFailed')}</div>
        </div>
      </div>
    );
  }

  const chats = data?.chats || [];

  if (chats.length === 0) {
    return (
      <div className="h-full bg-gray-50 border-l border-gray-200 p-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">{t('portfolio:chatSidebar.title')}</h3>
        <div className="flex items-center justify-center h-full">
          <div className="text-gray-500 text-center">
            <p>{t('portfolio:chatSidebar.noHistory')}</p>
            <p className="text-sm mt-2">{t('portfolio:chatSidebar.addSymbolsHint')}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full bg-gray-50 border-l border-gray-200 flex flex-col">
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">{t('portfolio:chatSidebar.title')}</h3>
        <p className="text-sm text-gray-500 mt-1">{t('portfolio:chatSidebar.symbolsTracked', { count: chats.length })}</p>
      </div>

      {/* Filters Section */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <SymbolFilter
          selectedSymbol={selectedSymbol}
          onSymbolChange={setSelectedSymbol}
          availableSymbols={availableSymbols}
        />
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          onClear={() => {
            setStartDate("");
            setEndDate("");
          }}
        />
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chats.map((chat) => {
          const isExpanded = expandedChats.has(chat.chat_id);
          const symbol = chat.symbol;
          const latestTimestamp = chat.latest_timestamp
            ? new Date(chat.latest_timestamp).toLocaleString()
            : t('portfolio:chatSidebar.unknownTime');
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
                      {t('portfolio:chatSidebar.analysesCount', { count: chat.message_count })}
                    </span>
                  </div>
                  <div className="text-sm text-gray-500 mt-1">{t('portfolio:chatSidebar.lastUpdated', { time: latestTimestamp })}</div>
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
                  {chat.messages.map((message, index) => {
                    const isToolMessage = message.source === "tool";
                    const isAssistant = message.role === "assistant";
                    const timestamp = new Date(message.timestamp).toLocaleString("en-US", {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    });

                    return (
                      <div
                        key={`${message.timestamp}-${index}`}
                        className="px-4 py-3 border-b border-gray-100 last:border-b-0"
                      >
                        <div className="flex items-start gap-3">
                          {/* Avatar */}
                          <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                            isToolMessage
                              ? "bg-amber-100"
                              : isAssistant
                              ? "bg-blue-100"
                              : "bg-gray-100"
                          }`}>
                            {isToolMessage ? (
                              <svg
                                className="w-4 h-4 text-amber-600"
                                fill="none"
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth="2"
                                viewBox="0 0 24 24"
                                stroke="currentColor"
                              >
                                <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
                                <path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
                              </svg>
                            ) : (
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
                            )}
                          </div>

                          {/* Message Content */}
                          <div className="flex-1 min-w-0">
                            {/* Timestamp */}
                            <div className="text-xs text-gray-500 mb-1">{timestamp}</div>

                            {/* Tool Badge */}
                            {isToolMessage && (
                              <div className="mb-2">
                                <span className="inline-flex items-center px-2 py-1 text-xs font-medium rounded-md bg-amber-100 text-amber-800">
                                  🛠️ Tool Execution
                                </span>
                              </div>
                            )}

                            {/* Message Text with Markdown */}
                            <div className="prose prose-sm max-w-none text-gray-900">
                              <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                rehypePlugins={[rehypeRaw]}
                                components={{
                                  // Customize markdown rendering
                                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                                  ul: ({ children }) => <ul className="list-disc pl-5 mb-2">{children}</ul>,
                                  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2">{children}</ol>,
                                  code: ({ inline, children }: any) =>
                                    inline ? (
                                      <code className="px-1 py-0.5 bg-gray-100 rounded text-xs font-mono">
                                        {children}
                                      </code>
                                    ) : (
                                      <code className="block p-2 bg-gray-100 rounded text-xs font-mono overflow-x-auto">
                                        {children}
                                      </code>
                                    ),
                                }}
                              >
                                {message.content}
                              </ReactMarkdown>
                            </div>

                            {/* Metadata */}
                            {message.metadata?.key_levels && message.metadata.key_levels.length > 0 && (
                              <div className="mt-2 text-xs text-gray-500">
                                <span className="font-medium">{t('portfolio:chatSidebar.keyLevels')}: </span>
                                {message.metadata.key_levels
                                  .map((level) => `$${level.toFixed(2)}`)
                                  .join(", ")}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
