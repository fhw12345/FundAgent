import { useState, useMemo, useCallback, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { marketService, TimeInterval } from "../services/market";
import { useChatManager } from "./chat/useChatManager";
import { useAnalysis, useButtonAnalysis } from "./chat/useAnalysis";
import { ChatMessages } from "./chat/ChatMessages";
import { ChatInput } from "./chat/ChatInput";
import { ChartPanel } from "./chat/ChartPanel";
import { ChatSidebar } from "./chat/ChatSidebar";
import { useChatRestoration } from "../hooks/useChatRestoration";
import { useUIStateSync } from "../hooks/useUIStateSync";
import type { FibonacciMetadata } from "../utils/analysisMetadataExtractor";
import { getPeriodForInterval } from "../utils/dateRangeCalculator";
import type { ModelSettings } from "../types/models";

export function EnhancedChatInterface() {
  const [message, setMessage] = useState("");
  const [currentSymbol, setCurrentSymbol] = useState("");
  const [currentCompanyName, setCurrentCompanyName] = useState("");
  const [selectedInterval, setSelectedInterval] = useState<TimeInterval>("1d");
  const [dateRangeStart, setDateRangeStart] = useState("");
  const [dateRangeEnd, setDateRangeEnd] = useState("");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isChartCollapsed, setIsChartCollapsed] = useState(false);

  // Mobile panel visibility (overlays on mobile)
  const [isMobileSidebarVisible, setIsMobileSidebarVisible] = useState(false);
  const [isMobileChartVisible, setIsMobileChartVisible] = useState(false);

  // LLM Model settings
  const [modelSettings, setModelSettings] = useState<ModelSettings>({
    model: "qwen-plus",
    thinking_enabled: false,
    max_tokens: 3000,
    debug_enabled: false,
  });

  // Agent mode: v3 = Agent (auto tools), v2 = Copilot (manual tools)
  const [agentMode, setAgentMode] = useState<"v2" | "v3">("v3");

  // Memoize selectedDateRange object to prevent recreation on every render
  const selectedDateRange = useMemo(
    () => ({ start: dateRangeStart, end: dateRangeEnd }),
    [dateRangeStart, dateRangeEnd],
  );

  // Stable setter for date range
  const setSelectedDateRange = useCallback(
    (range: { start: string; end: string }) => {
      setDateRangeStart(range.start);
      setDateRangeEnd(range.end);
    },
    [],
  );

  const { messages, setMessages, chatId, setChatId } = useChatManager();

  // Chat restoration hook
  const { restoreChat } = useChatRestoration({
    setMessages,
    setCurrentSymbol,
    setCurrentCompanyName,
    setSelectedInterval,
    setSelectedDateRange,
    setChatId,
  });

  // Auto-sync UI state to MongoDB (debounced)
  useUIStateSync({
    activeChatId: chatId,
    currentSymbol,
    selectedInterval,
    selectedDateRange,
  });

  // Extract Fibonacci analysis for the current symbol AND timeframe
  const currentFibonacciAnalysis = useMemo(() => {
    if (!currentSymbol) return null;

    console.log("🔍 Searching for Fibonacci data:", {
      currentSymbol,
      selectedInterval,
      totalMessages: messages.length,
    });

    // Find the most recent Fibonacci analysis for current symbol AND timeframe
    // Iterate backwards without creating array copy for better performance
    let fibMessage = null;
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (
        msg.role === "assistant" &&
        msg.analysis_data &&
        msg.analysis_data.symbol === currentSymbol &&
        msg.analysis_data.fibonacci_levels &&
        msg.analysis_data.timeframe === selectedInterval
      ) {
        fibMessage = msg;
        break;
      }
    }

    console.log("📊 Fibonacci analysis result:", {
      found: !!fibMessage,
      fibonacciData: fibMessage?.analysis_data,
    });

    // Type guard to ensure proper typing
    if (!fibMessage?.analysis_data) return null;
    return fibMessage.analysis_data as unknown as FibonacciMetadata;
  }, [messages, currentSymbol, selectedInterval]);

  // Chat mutation for user messages
  const chatMutation = useAnalysis(
    currentSymbol,
    selectedDateRange,
    setMessages,
    setSelectedDateRange,
    selectedInterval,
    chatId,
    setChatId,
    modelSettings,
    agentMode, // Pass agent mode
  );

  // Button analysis mutation for quick analysis buttons
  const buttonMutation = useButtonAnalysis(
    currentSymbol,
    selectedDateRange,
    setMessages,
    setSelectedDateRange,
    selectedInterval,
    chatId,
    setChatId,
  );

  const priceDataQuery = useQuery({
    queryKey: [
      "priceData",
      currentSymbol,
      selectedInterval,
      selectedDateRange.start,
      selectedDateRange.end,
    ],
    queryFn: () =>
      marketService.getPriceData(currentSymbol, {
        interval: selectedInterval,
        period:
          selectedDateRange.start && selectedDateRange.end
            ? undefined
            : getPeriodForInterval(selectedInterval),
        start_date: selectedDateRange.start || undefined,
        end_date: selectedDateRange.end || undefined,
      }),
    enabled: !!currentSymbol,
    staleTime: 30000,
    refetchInterval: 60000,
    retry: false,
  });

  const handleSymbolSelect = useCallback((symbol: string, name: string) => {
    setCurrentSymbol(symbol);
    setCurrentCompanyName(name);

    // Calculate date range for current interval
    const today = new Date();
    let daysBack: number;

    switch (selectedInterval) {
      case "1h":
        daysBack = 30;
        break;
      case "1w":
        daysBack = 365;
        break;
      case "1mo":
        daysBack = 730;
        break;
      default:
        daysBack = 180;
    }

    const startDate = new Date(today.getTime() - daysBack * 24 * 60 * 60 * 1000);
    setDateRangeStart(startDate.toISOString().split("T")[0]);
    setDateRangeEnd(today.toISOString().split("T")[0]);
  }, [selectedInterval]);

  const handleIntervalChange = useCallback((interval: TimeInterval) => {
    setSelectedInterval(interval);

    // Calculate appropriate date range for this interval
    const today = new Date();
    let daysBack: number;

    switch (interval) {
      case "1h":
        daysBack = 30; // 1-hour interval: last 30 days
        break;
      case "1w":
        daysBack = 365; // 1-week interval: last 1 year
        break;
      case "1mo":
        daysBack = 730; // 1-month interval: last 2 years
        break;
      default:
        daysBack = 180; // 1-day interval (default): last 6 months
    }

    const startDate = new Date(today.getTime() - daysBack * 24 * 60 * 60 * 1000);
    setDateRangeStart(startDate.toISOString().split("T")[0]);
    setDateRangeEnd(today.toISOString().split("T")[0]);
  }, []);

  const handleDateRangeSelect = useCallback(
    (startDate: string, endDate: string) => {
      setDateRangeStart(startDate);
      setDateRangeEnd(endDate);
    },
    [],
  );

  const handleQuickAnalysis = useCallback(
    (type: "fibonacci" | "fundamentals" | "macro" | "stochastic") => {
      // Generate user message describing the analysis request
      let userMessage = "";

      if (type === "fibonacci") {
        userMessage = `Start Fibonacci analysis for ${currentSymbol || "symbol"} on ${selectedInterval} period${selectedDateRange.start && selectedDateRange.end ? ` from ${selectedDateRange.start} to ${selectedDateRange.end}` : ""}`;
      } else if (type === "fundamentals") {
        userMessage = `Get fundamentals for ${currentSymbol || "symbol"}`;
      } else if (type === "macro") {
        userMessage = "Analyze macro market sentiment";
      } else if (type === "stochastic") {
        userMessage = `Start Stochastic oscillator analysis for ${currentSymbol || "symbol"} on ${selectedInterval} period${selectedDateRange.start && selectedDateRange.end ? ` from ${selectedDateRange.start} to ${selectedDateRange.end}` : ""}`;
      }

      // Add user message to chat (triggers auto-scroll to user message position)
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: userMessage,
          timestamp: new Date().toISOString(),
        },
      ]);

      // Trigger analysis (assistant response will appear below)
      buttonMutation.mutate(type);
    },
    [
      buttonMutation,
      setMessages,
      currentSymbol,
      selectedInterval,
      selectedDateRange,
    ],
  );

  // Old complex pattern matching logic removed
  const handleSendMessage = useCallback(() => {
    if (!message.trim()) return;
    chatMutation.mutate(message); // All user messages go to LLM
    setMessage("");
  }, [message, chatMutation]);

  const isRestoringRef = useRef(false);

  const handleChatSelect = useCallback(
    async (chatId: string) => {
      // Prevent concurrent restoration requests
      if (isRestoringRef.current) {
        console.log("⏭️ Skipping chat select: restoration in progress");
        return;
      }

      isRestoringRef.current = true;
      try {
        await restoreChat(chatId);
      } finally {
        isRestoringRef.current = false;
      }
    },
    [restoreChat],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setChatId(null);
    setCurrentSymbol("");
    setCurrentCompanyName("");
    setDateRangeStart("");
    setDateRangeEnd("");
  }, [setMessages, setChatId]);

  return (
    <div className="bg-white overflow-hidden max-h-screen">
      {/* Desktop: CSS Grid with fixed sidebar + flexible chat + narrow chart */}
      {/* Mobile: Flex column with overlays */}
      <div className="mx-auto">
        <div className="relative">
          <div
            className="flex flex-col lg:grid lg:gap-0 h-[calc(100vh-5rem)]"
            style={{
              gridTemplateColumns: `${isSidebarCollapsed ? '48px' : '240px'} minmax(600px, 1fr) ${isChartCollapsed ? '48px' : 'minmax(400px, 600px)'}`,
            }}
          >
            {/* Chat History Sidebar - Mobile: overlay, Desktop: fixed 240px column */}
            <div
              className={`${
                isMobileSidebarVisible
                  ? "absolute top-0 left-0 z-20 h-full w-64 bg-white shadow-2xl"
                  : "hidden"
              } lg:block lg:relative lg:z-0 lg:w-auto lg:border-r lg:border-gray-300 lg:h-full lg:overflow-hidden`}
            >
              <ChatSidebar
                activeChatId={chatId}
                onChatSelect={(id) => void handleChatSelect(id)}
                onNewChat={handleNewChat}
                isCollapsed={isSidebarCollapsed}
                onToggleCollapse={() =>
                  setIsSidebarCollapsed(!isSidebarCollapsed)
                }
              />
            </div>

            {/* Mobile sidebar backdrop */}
            {isMobileSidebarVisible && (
              <div
                role="button"
                tabIndex={0}
                className="absolute inset-0 bg-black/50 z-10 lg:hidden"
                onClick={() => setIsMobileSidebarVisible(false)}
                onKeyDown={(e) => {
                  if (e.key === "Escape" || e.key === "Enter") {
                    setIsMobileSidebarVisible(false);
                  }
                }}
                aria-label="Close sidebar"
              />
            )}

            {/* Chat Panel - Mobile: primary full-width, Desktop: flexible middle column */}
            <div className="flex flex-col h-full w-full lg:w-auto lg:min-w-[600px] border-r border-gray-300 relative bg-gray-50 overflow-hidden">
              {/* Mobile toggle buttons - only show when panels are closed */}
              {!isMobileChartVisible && (
                <div className="flex lg:hidden absolute top-2 left-2 right-2 z-10 gap-2">
                  <button
                    onClick={() => setIsMobileSidebarVisible(!isMobileSidebarVisible)}
                    className="px-3 py-1.5 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg shadow-sm text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    {isMobileSidebarVisible ? "← Hide" : "← Chats"}
                  </button>
                  <button
                    onClick={() => setIsMobileChartVisible(true)}
                    className="ml-auto px-3 py-1.5 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg shadow-sm text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Chart →
                  </button>
                </div>
              )}

              {/* Add padding-top to prevent toggle buttons from covering messages */}
              <div className="pt-12 lg:pt-0 flex flex-col h-full">
                <ChatMessages
                  messages={messages}
                  isAnalysisPending={
                    chatMutation.isPending || buttonMutation.isPending
                  }
                />

                {/* Agent Mode Toggle - Only enabled when starting new chat */}
                <div className="flex-shrink-0 px-4 py-2 border-t border-gray-100 bg-gray-50/50">
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-gray-600 font-medium">Mode:</span>
                    <button
                      onClick={() => setAgentMode("v3")}
                      disabled={!!chatId}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                        agentMode === "v3"
                          ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md"
                          : "bg-white text-gray-700 hover:bg-gray-100"
                      } ${
                        chatId
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"
                      }`}
                      title={
                        chatId
                          ? "Mode locked for this chat"
                          : "Agent mode (auto tool calling)"
                      }
                    >
                      🤖 Agent
                    </button>
                    <button
                      onClick={() => setAgentMode("v2")}
                      disabled={!!chatId}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                        agentMode === "v2"
                          ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-md"
                          : "bg-white text-gray-700 hover:bg-gray-100"
                      } ${
                        chatId
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"
                      }`}
                      title={
                        chatId
                          ? "Mode locked for this chat"
                          : "Copilot mode (manual tools)"
                      }
                    >
                      👤 Copilot
                    </button>
                    {chatId && (
                      <span className="ml-auto text-xs text-gray-500 italic">
                        Mode locked for this chat
                      </span>
                    )}
                  </div>
                </div>

                <ChatInput
                  message={message}
                  setMessage={setMessage}
                  onSendMessage={handleSendMessage}
                  isPending={chatMutation.isPending || buttonMutation.isPending}
                  currentSymbol={currentSymbol}
                  messages={messages}
                  modelSettings={modelSettings}
                  onModelSettingsChange={setModelSettings}
                />
              </div>
            </div>

            {/* Chart Panel - Mobile: slide-in drawer (80% width), Desktop: fixed column */}
            <div
              className={`${
                isMobileChartVisible
                  ? "absolute top-0 right-0 z-30 h-full w-4/5 bg-white shadow-2xl transform transition-transform duration-300"
                  : "hidden lg:block lg:relative lg:z-0 lg:w-auto lg:h-full lg:overflow-hidden"
              }`}
            >
              {/* Mobile close button for chart panel */}
              {isMobileChartVisible && (
                <div className="lg:hidden absolute top-2 left-2 right-2 z-40 flex justify-between items-center px-2">
                  <button
                    onClick={() => setIsMobileChartVisible(false)}
                    className="px-4 py-2 bg-white/95 backdrop-blur-sm border border-gray-300 rounded-lg shadow-lg text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center gap-2"
                  >
                    ← Back to Chat
                  </button>
                  <button
                    onClick={() => setIsMobileChartVisible(false)}
                    className="w-9 h-9 bg-white/95 backdrop-blur-sm border border-gray-300 rounded-lg shadow-lg text-gray-700 hover:bg-gray-50 flex items-center justify-center font-semibold"
                    aria-label="Close chart"
                  >
                    ✕
                  </button>
                </div>
              )}

              <ChartPanel
                currentSymbol={currentSymbol}
                currentCompanyName={currentCompanyName}
                priceDataQuery={priceDataQuery}
                selectedInterval={selectedInterval}
                selectedDateRange={selectedDateRange}
                analysisMutation={buttonMutation}
                fibonacciAnalysis={currentFibonacciAnalysis}
                handleSymbolSelect={handleSymbolSelect}
                handleIntervalChange={handleIntervalChange}
                handleDateRangeSelect={handleDateRangeSelect}
                handleQuickAnalysis={handleQuickAnalysis}
                isCollapsed={isChartCollapsed}
                onToggleCollapse={() => setIsChartCollapsed(!isChartCollapsed)}
              />
            </div>

            {/* Mobile chart backdrop - allows clicking to close */}
            {isMobileChartVisible && (
              <div
                role="button"
                tabIndex={0}
                className="absolute inset-0 bg-black/60 z-20 lg:hidden"
                onClick={() => setIsMobileChartVisible(false)}
                onKeyDown={(e) => {
                  if (e.key === "Escape" || e.key === "Enter") {
                    setIsMobileChartVisible(false);
                  }
                }}
                aria-label="Close chart"
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
