import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { analysisService } from "../services/analysis";
import type { ChatMessage } from "../types/api";
import {
  formatFibonacciResponse,
  formatMacroResponse,
  formatFundamentalsResponse,
  formatStochasticResponse,
} from "./chat/analysisFormatters";
import { QuickAnalysisPanel } from "./chat/QuickAnalysisPanel";
import { DateRangeControls } from "./chat/DateRangeControls";
import { ChatMessageInput } from "./chat/ChatMessageInput";

export function ChatInterface() {
  const [message, setMessage] = useState("");
  const [currentSymbol, setCurrentSymbol] = useState("");
  const [startDate, setStartDate] = useState(() => {
    const date = new Date();
    date.setMonth(date.getMonth() - 6); // Default to 6 months ago
    return date.toISOString().split("T")[0];
  });
  const [endDate, setEndDate] = useState(() => {
    return new Date().toISOString().split("T")[0]; // Default to today
  });
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: `Hello! I'm your AI financial analysis assistant. I can help you with:

• **📈 Fibonacci Analysis** - Technical retracement levels and swing points
• **🌍 Macro Sentiment** - VIX, market sentiment, and sector rotation
• **📊 Stock Fundamentals** - Company metrics and valuation data
• **⚡ Stochastic Oscillator** - Overbought/oversold conditions and momentum
• **📉 Chart Generation** - Visual analysis with technical indicators

**Quick Start:** Enter a stock symbol below (e.g., AAPL), select date range, then click any analysis button. Or type your request naturally in the chat.`,
      timestamp: new Date().toISOString(),
    },
  ]);

  const analysisMutation = useMutation({
    mutationFn: async (userMessage: string) => {
      const intent = analysisService.parseAnalysisIntent(userMessage);

      switch (intent.type) {
        case "fibonacci": {
          if (!intent.symbol) {
            throw new Error(
              'Please specify a stock symbol for Fibonacci analysis (e.g., "Show Fibonacci analysis for AAPL")',
            );
          }

          const startDate = intent.start_date;
          const endDate = intent.end_date;

          const finalStartDate =
            startDate ||
            new Date(Date.now() - 6 * 30 * 24 * 60 * 60 * 1000)
              .toISOString()
              .split("T")[0];
          const finalEndDate =
            endDate || new Date().toISOString().split("T")[0];

          const fibResult = await analysisService.fibonacciAnalysis({
            symbol: intent.symbol,
            start_date: finalStartDate,
            end_date: finalEndDate,
            include_chart: true,
          });
          return {
            type: "fibonacci",
            content: formatFibonacciResponse(fibResult),
            analysis_data: fibResult,
          };
        }

        case "macro": {
          const macroResult = await analysisService.macroSentimentAnalysis({
            include_sectors: true,
            include_indices: true,
          });
          return {
            type: "macro",
            content: formatMacroResponse(macroResult),
            analysis_data: macroResult,
          };
        }

        case "fundamentals": {
          if (!intent.symbol) {
            throw new Error(
              'Please specify a stock symbol for fundamental analysis (e.g., "Give me fundamentals for TSLA")',
            );
          }
          const fundResult = await analysisService.stockFundamentals({
            symbol: intent.symbol,
          });
          return {
            type: "fundamentals",
            content: formatFundamentalsResponse(fundResult),
            analysis_data: fundResult,
          };
        }

        case "chart": {
          if (!intent.symbol) {
            throw new Error(
              'Please specify a stock symbol for chart generation (e.g., "Show chart for AAPL")',
            );
          }
          const chartResult = await analysisService.generateChart({
            symbol: intent.symbol,
            start_date: intent.start_date,
            end_date: intent.end_date,
            chart_type: "fibonacci",
            include_indicators: true,
          });
          return {
            type: "chart",
            content: `Generated ${chartResult.chart_type} chart for ${chartResult.symbol}`,
            analysis_data: chartResult,
            chart_url: chartResult.chart_url,
          };
        }

        default:
          throw new Error(`I can help you with:
• **Fibonacci Analysis** - "Show Fibonacci analysis for AAPL"
• **Macro Sentiment** - "What's the current market sentiment?"
• **Stock Fundamentals** - "Give me fundamentals for TSLA"
• **Chart Generation** - "Show chart for NVDA"
• **Stochastic Analysis** - Use the Stochastic button below

Please specify a stock symbol and analysis type.`);
      }
    },
    onMutate: (newMessage) => {
      const userMessage: ChatMessage = {
        role: "user",
        content: newMessage,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMessage]);
      setMessage("");
      return { userMessage };
    },
    onSuccess: (response) => {
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.content,
        timestamp: new Date().toISOString(),
        chart_url: response.chart_url,
        analysis_data: response.analysis_data,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    },
    onError: (error: any) => {
      let errorContent = "Unknown error occurred. Please try again.";

      if (error?.response?.data?.detail) {
        errorContent = error.response.data.detail;
      } else if (error?.response?.status === 400) {
        if (error?.response?.data?.detail) {
          errorContent = error.response.data.detail;
        } else {
          errorContent =
            "Invalid request. Please check your input and try again.";
        }
      } else if (error?.response?.status === 500) {
        // Server error
        errorContent =
          "Server error occurred. The analysis service may be temporarily unavailable.";
      } else if (error?.message) {
        // Axios error or other error with message
        errorContent = error.message;
      }

      const errorMessage: ChatMessage = {
        role: "assistant",
        content: `❌ **Error**: ${errorContent}`,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    },
  });

  const handleSendMessage = () => {
    if (!message.trim()) return;
    analysisMutation.mutate(message);
  };

  // Direct action mutation for button-based analyses
  const directActionMutation = useMutation({
    mutationFn: async (actionData: {
      type: string;
      symbol?: string;
      startDate?: string;
      endDate?: string;
    }) => {
      const { type, symbol, startDate, endDate } = actionData;

      switch (type) {
        case "fibonacci": {
          if (!symbol) {
            throw new Error("Symbol is required for Fibonacci analysis");
          }
          const fibResult = await analysisService.fibonacciAnalysis({
            symbol,
            start_date: startDate,
            end_date: endDate,
            include_chart: true,
          });
          return {
            type: "fibonacci",
            content: formatFibonacciResponse(fibResult),
            analysis_data: fibResult,
          };
        }

        case "macro": {
          const macroResult = await analysisService.macroSentimentAnalysis({
            include_sectors: true,
            include_indices: true,
          });
          return {
            type: "macro",
            content: formatMacroResponse(macroResult),
            analysis_data: macroResult,
          };
        }

        case "fundamentals": {
          if (!symbol) {
            throw new Error("Symbol is required for fundamentals analysis");
          }
          const fundResult = await analysisService.stockFundamentals({
            symbol,
          });
          return {
            type: "fundamentals",
            content: formatFundamentalsResponse(fundResult),
            analysis_data: fundResult,
          };
        }

        case "stochastic": {
          if (!symbol) {
            throw new Error("Symbol is required for stochastic analysis");
          }
          const stochResult = await analysisService.stochasticAnalysis({
            symbol,
            start_date: startDate,
            end_date: endDate,
            timeframe: "1d", // Default timeframe
            k_period: 14,
            d_period: 3,
          });
          return {
            type: "stochastic",
            content: formatStochasticResponse(stochResult),
            analysis_data: stochResult,
          };
        }

        case "chart": {
          if (!symbol) {
            throw new Error("Symbol is required for chart generation");
          }
          const chartResult = await analysisService.generateChart({
            symbol,
            start_date: startDate,
            end_date: endDate,
            chart_type: "fibonacci",
            include_indicators: true,
          });
          return {
            type: "chart",
            content: `Generated ${chartResult.chart_type} chart for ${chartResult.symbol}`,
            analysis_data: chartResult,
            chart_url: chartResult.chart_url,
          };
        }

        default:
          throw new Error(`Unknown action type: ${type}`);
      }
    },
    onMutate: (actionData) => {
      // Add a user message showing what action was requested
      const actionName =
        actionData.type.charAt(0).toUpperCase() + actionData.type.slice(1);
      const symbolPart = actionData.symbol ? ` for ${actionData.symbol}` : "";
      setMessages((prev) => [
        ...prev,
        {
          role: "user",
          content: `${actionName} Analysis${symbolPart}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    },
    onSuccess: (response) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.content,
          timestamp: new Date().toISOString(),
          analysis_data: response.analysis_data,
        },
      ]);
    },
    onError: (error: any) => {
      const errorContent =
        error?.response?.data?.detail || error.message || "Unknown error";
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `❌ **Error**: ${errorContent}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    },
  });

  const handleDirectAction = (
    actionType: "fibonacci" | "fundamentals" | "chart" | "macro" | "stochastic",
  ) => {
    if (actionType === "macro") {
      // Macro analysis doesn't need a symbol
      directActionMutation.mutate({ type: "macro" });
      return;
    }

    if (!currentSymbol.trim()) {
      // Focus on symbol input if empty
      const symbolInput = document.getElementById("symbol-input");
      symbolInput?.focus();
      return;
    }

    // Basic symbol validation
    const symbol = currentSymbol.trim().toUpperCase();
    if (symbol.length < 1 || symbol.length > 10) {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content:
          "❌ **Error**: Stock symbol must be between 1-10 characters (e.g., AAPL, TSLA, MSFT)",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      return;
    }

    // Check for invalid characters
    if (!/^[A-Z0-9.-]+$/.test(symbol)) {
      const errorMessage: ChatMessage = {
        role: "assistant",
        content:
          "❌ **Error**: Stock symbol contains invalid characters. Use only letters, numbers, dots, and hyphens.",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
      return;
    }

    // Execute direct action with current UI state
    directActionMutation.mutate({
      type: actionType,
      symbol,
      startDate,
      endDate,
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-sm border h-[600px] flex flex-col">
      {/* Chat Header */}
      <div className="border-b p-4">
        <h3 className="text-lg font-medium text-gray-900">
          Financial Analysis Chat
        </h3>
        <p className="text-sm text-gray-500">
          Ask me about stocks, market analysis, or financial data
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                msg.role === "user"
                  ? "bg-blue-500 text-white"
                  : "bg-gray-100 text-gray-900"
              }`}
            >
              <div className="markdown-content text-sm max-w-none">
                {msg.role === "user" ? (
                  <p className="text-white m-0">{msg.content}</p>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>

              {/* Chart Display */}
              {msg.chart_url && (
                <div className="mt-3">
                  <img
                    src={msg.chart_url}
                    alt="Financial Chart"
                    className="rounded-md border max-w-full h-auto"
                  />
                </div>
              )}

              {/* Analysis Data */}
              {msg.analysis_data && (
                <div className="mt-3 p-2 bg-gray-50 rounded text-xs">
                  <pre className="text-gray-600 overflow-x-auto">
                    {JSON.stringify(msg.analysis_data, null, 2)}
                  </pre>
                </div>
              )}

              <div
                className={`text-xs mt-1 ${
                  msg.role === "user" ? "text-blue-200" : "text-gray-500"
                }`}
              >
                {new Date(msg.timestamp).toLocaleTimeString("en-US", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {(analysisMutation.isPending || directActionMutation.isPending) && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-2 rounded-lg">
              <div className="flex items-center space-x-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-gray-600">Analyzing...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Analysis Controls */}
      <div className="border-t p-4">
        {/* Symbol and Date Range Inputs */}
        <DateRangeControls
          currentSymbol={currentSymbol}
          startDate={startDate}
          endDate={endDate}
          onSymbolChange={setCurrentSymbol}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
        />

        {/* Quick Actions */}
        <QuickAnalysisPanel
          currentSymbol={currentSymbol}
          onAnalysisClick={handleDirectAction}
          disabled={directActionMutation.isPending}
        />

        {/* Message Input */}
        <ChatMessageInput
          message={message}
          onMessageChange={setMessage}
          onSend={handleSendMessage}
          disabled={
            analysisMutation.isPending || directActionMutation.isPending
          }
          loading={analysisMutation.isPending || directActionMutation.isPending}
        />
      </div>
    </div>
  );
}
