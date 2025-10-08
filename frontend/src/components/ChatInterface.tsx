import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Send,
  BarChart3,
  TrendingUp,
  DollarSign,
  Loader2,
  LineChart,
  Activity,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { analysisService } from "../services/analysis";
import type { ChatMessage } from "../types/api";
import type {
  FibonacciAnalysisResponse,
  MacroSentimentResponse,
  StockFundamentalsResponse,
  StochasticAnalysisResponse,
} from "../services/analysis";

// Formatting functions for analysis responses
function formatFibonacciResponse(result: FibonacciAnalysisResponse): string {
  const keyLevels = result.fibonacci_levels.filter(
    (level) => level.is_key_level,
  );

  return `## Fibonacci Analysis - ${result.symbol}

**Current Price:** $${result.current_price.toFixed(2)}
**Trend Direction:** ${result.market_structure.trend_direction}
**Confidence Score:** ${(result.confidence_score * 100).toFixed(1)}%

### Key Fibonacci Levels:
${keyLevels
  .map((level) => `• **${level.percentage}** - $${level.price.toFixed(2)}`)
  .join("\n")}

### Market Structure:
• **Swing High:** $${result.market_structure.swing_high.price.toFixed(2)} (${result.market_structure.swing_high.date})
• **Swing Low:** $${result.market_structure.swing_low.price.toFixed(2)} (${result.market_structure.swing_low.date})
• **Structure Quality:** ${result.market_structure.structure_quality}

### Analysis Summary:
${result.analysis_summary}

### Key Insights:
${result.key_insights.map((insight) => `• ${insight}`).join("\n")}
`;
}

function formatMacroResponse(result: MacroSentimentResponse): string {
  const topSectors = Object.entries(result.sector_performance)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);

  const bottomSectors = Object.entries(result.sector_performance)
    .sort(([, a], [, b]) => a - b)
    .slice(0, 3);

  return `## Macro Market Sentiment Analysis

**Overall Sentiment:** ${result.market_sentiment.toUpperCase()}
**VIX Level:** ${result.vix_level.toFixed(2)} (${result.vix_interpretation})
**Fear/Greed Score:** ${result.fear_greed_score}/100

### Major Indices Performance:
${Object.entries(result.major_indices)
  .map(
    ([index, change]) =>
      `• **${index}:** ${change > 0 ? "+" : ""}${change.toFixed(2)}%`,
  )
  .join("\n")}

### Top Performing Sectors:
${topSectors
  .map(([sector, change]) => `• **${sector}:** +${change.toFixed(2)}%`)
  .join("\n")}

### Bottom Performing Sectors:
${bottomSectors
  .map(([sector, change]) => `• **${sector}:** ${change.toFixed(2)}%`)
  .join("\n")}

### Market Outlook:
${result.market_outlook}

### Key Factors:
${result.key_factors.map((factor) => `• ${factor}`).join("\n")}
`;
}

function formatFundamentalsResponse(result: StockFundamentalsResponse): string {
  const priceChange = result.price_change_percent > 0 ? "+" : "";

  return `## Stock Fundamentals - ${result.symbol}

**Company:** ${result.company_name}
**Current Price:** $${result.current_price.toFixed(2)} (${priceChange}${result.price_change_percent.toFixed(2)}%)
**Market Cap:** $${(result.market_cap / 1_000_000_000).toFixed(2)}B

### Valuation Metrics:
${result.pe_ratio ? `• **P/E Ratio:** ${result.pe_ratio.toFixed(2)}` : ""}
${result.pb_ratio ? `• **P/B Ratio:** ${result.pb_ratio.toFixed(2)}` : ""}
${result.dividend_yield ? `• **Dividend Yield:** ${result.dividend_yield.toFixed(2)}%` : ""}
${result.beta ? `• **Beta:** ${result.beta.toFixed(2)}` : ""}

### Trading Data:
• **Volume:** ${result.volume.toLocaleString()} (Avg: ${result.avg_volume.toLocaleString()})
• **52-Week High:** $${result.fifty_two_week_high.toFixed(2)}
• **52-Week Low:** $${result.fifty_two_week_low.toFixed(2)}

### Summary:
${result.fundamental_summary}

### Key Metrics:
${result.key_metrics.map((metric) => `• ${metric}`).join("\n")}
`;
}

function formatStochasticResponse(result: StochasticAnalysisResponse): string {
  const signalEmoji =
    result.current_signal === "overbought"
      ? "📈"
      : result.current_signal === "oversold"
        ? "📉"
        : "➡️";

  // Get recent signals (last 3 signals)
  const recentSignals = result.signal_changes.slice(-3);

  return `## ${signalEmoji} Stochastic Oscillator Analysis - ${result.symbol}

**Current Price:** $${result.current_price.toFixed(2)}
**Analysis Period:** ${result.start_date || "Dynamic"} to ${result.end_date || "Current"} (${result.timeframe} timeframe)
**Parameters:** %K(${result.k_period}) %D(${result.d_period})

### Current Readings:
• **%K Line:** ${result.current_k.toFixed(2)}%
• **%D Line:** ${result.current_d.toFixed(2)}%
• **Signal:** ${result.current_signal.toUpperCase()} ${signalEmoji}

${
  recentSignals.length > 0
    ? `### Recent Signals:
${recentSignals.map((signal) => `• **${signal.type.toUpperCase()}**: ${signal.description}`).join("\n")}
`
    : ""
}

### Analysis Summary:
${result.analysis_summary}

### Key Insights:
${result.key_insights.map((insight) => `• ${insight}`).join("\n")}
`;
}

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
      // Parse user intent
      const intent = analysisService.parseAnalysisIntent(userMessage);

      switch (intent.type) {
        case "fibonacci":
          if (!intent.symbol) {
            throw new Error(
              'Please specify a stock symbol for Fibonacci analysis (e.g., "Show Fibonacci analysis for AAPL")',
            );
          }

          // Ensure we have dates for Fibonacci analysis
          const startDate = intent.start_date;
          const endDate = intent.end_date;

          // If no date range specified, default to last 6 months
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

        case "macro":
          const macroResult = await analysisService.macroSentimentAnalysis({
            include_sectors: true,
            include_indices: true,
          });
          return {
            type: "macro",
            content: formatMacroResponse(macroResult),
            analysis_data: macroResult,
          };

        case "fundamentals":
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

        case "chart":
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
    onMutate: async (newMessage) => {
      // Optimistically add user message
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
      // Add assistant response
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
      // Extract specific error message from API response
      let errorContent = "Unknown error occurred. Please try again.";

      if (error?.response?.data?.detail) {
        // FastAPI validation error or custom error message
        errorContent = error.response.data.detail;
      } else if (error?.response?.status === 400) {
        // Bad request - likely invalid symbol
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

  const handleQuickAction = (action: string) => {
    analysisMutation.mutate(action);
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
        case "fibonacci":
          const fibResult = await analysisService.fibonacciAnalysis({
            symbol: symbol!,
            start_date: startDate,
            end_date: endDate,
            include_chart: true,
          });
          return {
            type: "fibonacci",
            content: formatFibonacciResponse(fibResult),
            analysis_data: fibResult,
          };

        case "macro":
          const macroResult = await analysisService.macroSentimentAnalysis({
            include_sectors: true,
            include_indices: true,
          });
          return {
            type: "macro",
            content: formatMacroResponse(macroResult),
            analysis_data: macroResult,
          };

        case "fundamentals":
          const fundResult = await analysisService.stockFundamentals({
            symbol: symbol!,
          });
          return {
            type: "fundamentals",
            content: formatFundamentalsResponse(fundResult),
            analysis_data: fundResult,
          };

        case "stochastic":
          const stochResult = await analysisService.stochasticAnalysis({
            symbol: symbol!,
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

        case "chart":
          const chartResult = await analysisService.generateChart({
            symbol: symbol!,
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

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
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
                {formatTimestamp(msg.timestamp)}
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
        <div className="mb-4 space-y-3">
          <div className="flex space-x-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Stock Symbol
              </label>
              <input
                id="symbol-input"
                type="text"
                value={currentSymbol}
                onChange={(e) => setCurrentSymbol(e.target.value.toUpperCase())}
                placeholder="e.g., AAPL, TSLA, MSFT"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                maxLength={10}
              />
            </div>
            <div className="w-36">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                From Date
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <div className="w-36">
              <label className="block text-xs font-medium text-gray-700 mb-1">
                To Date
              </label>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Quick Date Range Buttons */}
          <div className="flex space-x-2">
            <span className="text-xs text-gray-500">Quick ranges:</span>
            <button
              onClick={() => {
                const end = new Date();
                const start = new Date();
                start.setMonth(start.getMonth() - 1);
                setStartDate(start.toISOString().split("T")[0]);
                setEndDate(end.toISOString().split("T")[0]);
              }}
              className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              1M
            </button>
            <button
              onClick={() => {
                const end = new Date();
                const start = new Date();
                start.setMonth(start.getMonth() - 3);
                setStartDate(start.toISOString().split("T")[0]);
                setEndDate(end.toISOString().split("T")[0]);
              }}
              className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              3M
            </button>
            <button
              onClick={() => {
                const end = new Date();
                const start = new Date();
                start.setMonth(start.getMonth() - 6);
                setStartDate(start.toISOString().split("T")[0]);
                setEndDate(end.toISOString().split("T")[0]);
              }}
              className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              6M
            </button>
            <button
              onClick={() => {
                const end = new Date();
                const start = new Date();
                start.setFullYear(start.getFullYear() - 1);
                setStartDate(start.toISOString().split("T")[0]);
                setEndDate(end.toISOString().split("T")[0]);
              }}
              className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              1Y
            </button>
            <button
              onClick={() => {
                const end = new Date();
                const start = new Date();
                start.setFullYear(start.getFullYear() - 2);
                setStartDate(start.toISOString().split("T")[0]);
                setEndDate(end.toISOString().split("T")[0]);
              }}
              className="text-xs px-2 py-1 text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded"
            >
              2Y
            </button>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-2">Quick Analysis:</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleDirectAction("fibonacci")}
              disabled={directActionMutation.isPending}
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
                currentSymbol.trim()
                  ? "bg-blue-100 text-blue-800 hover:bg-blue-200"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              <BarChart3 className="h-3 w-3 mr-1" />
              Fibonacci
            </button>
            <button
              onClick={() => handleDirectAction("macro")}
              disabled={directActionMutation.isPending}
              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 hover:bg-green-200 disabled:opacity-50"
            >
              <TrendingUp className="h-3 w-3 mr-1" />
              Macro
            </button>
            <button
              onClick={() => handleDirectAction("fundamentals")}
              disabled={directActionMutation.isPending}
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
                currentSymbol.trim()
                  ? "bg-purple-100 text-purple-800 hover:bg-purple-200"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              <DollarSign className="h-3 w-3 mr-1" />
              Fundamentals
            </button>
            <button
              onClick={() => handleDirectAction("chart")}
              disabled={directActionMutation.isPending}
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
                currentSymbol.trim()
                  ? "bg-orange-100 text-orange-800 hover:bg-orange-200"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              <LineChart className="h-3 w-3 mr-1" />
              Chart
            </button>
            <button
              onClick={() => handleDirectAction("stochastic")}
              disabled={directActionMutation.isPending}
              className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
                currentSymbol.trim()
                  ? "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"
                  : "bg-gray-100 text-gray-500 hover:bg-gray-200"
              }`}
            >
              <Activity className="h-3 w-3 mr-1" />
              Stochastic
            </button>
          </div>
        </div>

        {/* Message Input */}
        <div className="flex space-x-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) =>
              e.key === "Enter" && !e.shiftKey && handleSendMessage()
            }
            placeholder="Ask about stocks, Fibonacci analysis, market sentiment..."
            disabled={
              analysisMutation.isPending || directActionMutation.isPending
            }
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={handleSendMessage}
            disabled={
              !message.trim() ||
              analysisMutation.isPending ||
              directActionMutation.isPending
            }
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {analysisMutation.isPending || directActionMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
