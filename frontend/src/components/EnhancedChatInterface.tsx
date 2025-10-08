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

export function EnhancedChatInterface() {
  const [message, setMessage] = useState("");
  const [currentSymbol, setCurrentSymbol] = useState("");
  const [currentCompanyName, setCurrentCompanyName] = useState("");
  const [selectedInterval, setSelectedInterval] = useState<TimeInterval>("1d");
  const [dateRangeStart, setDateRangeStart] = useState("");
  const [dateRangeEnd, setDateRangeEnd] = useState("");
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

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
    const fibMessage = [...messages]
      .reverse()
      .find(
        (msg) =>
          msg.role === "assistant" &&
          msg.analysis_data &&
          msg.analysis_data.symbol === currentSymbol &&
          msg.analysis_data.fibonacci_levels &&
          msg.analysis_data.timeframe === selectedInterval,
      );

    console.log("📊 Fibonacci analysis result:", {
      found: !!fibMessage,
      fibonacciData: fibMessage?.analysis_data,
    });

    return fibMessage?.analysis_data as FibonacciMetadata | null;
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
    setDateRangeStart("");
    setDateRangeEnd("");
  }, []);

  const handleIntervalChange = useCallback((interval: TimeInterval) => {
    setSelectedInterval(interval);
    setDateRangeStart("");
    setDateRangeEnd("");
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
      // All button clicks go directly to analysis endpoints
      buttonMutation.mutate(type);
    },
    [buttonMutation.mutate],
  );

  // Old complex pattern matching logic removed
  const handleSendMessage = useCallback(() => {
    if (!message.trim()) return;
    chatMutation.mutate(message); // All user messages go to LLM
    setMessage("");
  }, [message, chatMutation.mutate]);

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
          <div className="flex h-[calc(100vh-10rem)]">
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
