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

  // LLM Model settings
  const [modelSettings, setModelSettings] = useState<ModelSettings>({
    model: "qwen-plus",
    thinking_enabled: false,
    max_tokens: 3000,
    debug_enabled: false,
  });

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
    <div className="bg-white">
      {/* Full-width trading interface with sidebar */}
      <div className="mx-auto">
        <div className="overflow-hidden">
          <div className="flex h-[calc(100vh-8rem)]">
            {/* Chat History Sidebar */}
            <ChatSidebar
              activeChatId={chatId}
              onChatSelect={(id) => void handleChatSelect(id)}
              onNewChat={handleNewChat}
              isCollapsed={isSidebarCollapsed}
              onToggleCollapse={() =>
                setIsSidebarCollapsed(!isSidebarCollapsed)
              }
            />

            {/* Chat Panel */}
            <div className="flex flex-col flex-1 lg:w-2/5 border-r border-gray-200">
              <ChatMessages
                messages={messages}
                isAnalysisPending={
                  chatMutation.isPending || buttonMutation.isPending
                }
              />

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

            {/* Chart Panel - Optimized width */}
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
            />
          </div>
        </div>
      </div>
    </div>
  );
}
