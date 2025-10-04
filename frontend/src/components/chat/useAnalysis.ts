/**
 * useAnalysis Hook
 *
 * SIMPLIFIED VERSION:
 * - User chat messages → LLM (no pattern matching)
 * - Button clicks → Direct analysis endpoints
 */

import { flushSync } from "react-dom";
import { useMutation } from "@tanstack/react-query";
import { analysisService } from "../../services/analysis";
import { chatService } from "../../services/api";
import type {
  FibonacciAnalysisResponse,
  MacroSentimentResponse,
  StockFundamentalsResponse,
  StochasticAnalysisResponse,
} from "../../services/analysis";

// Formatting functions
function formatFibonacciResponse(result: FibonacciAnalysisResponse): string {
  const keyLevels = result.fibonacci_levels.filter(
    (level) => level.is_key_level,
  );

  // Format Big 3 trends with Fibonacci levels
  let bigThreeSection = "";
  if (result.raw_data?.top_trends && result.raw_data.top_trends.length > 0) {
    bigThreeSection = `
### 🎯 Big 3 Trends with Fibonacci Levels:

${result.raw_data.top_trends
  .slice(0, 3)
  .map((trend: any, index: number) => {
    const trendType = trend.type.includes("Uptrend") ? "📈" : "📉";
    const magnitude = (trend.magnitude || 0).toFixed(1);
    const isMainTrend = index === 0;

    const fibLevels = trend.fibonacci_levels || [];
    const keyFibLevels = fibLevels.filter((level: any) => level.is_key_level);

    let fibSection = "";
    if (keyFibLevels.length > 0) {
      fibSection = keyFibLevels
        .map(
          (level: any) =>
            `   • **${level.percentage}** - $${level.price.toFixed(2)}`,
        )
        .join("\n");
    } else if (fibLevels.length > 0) {
      fibSection = fibLevels
        .map(
          (level: any) =>
            `   • **${level.percentage}** - $${level.price.toFixed(2)}${level.is_key_level ? " 🌟" : ""}`,
        )
        .join("\n");
    } else {
      fibSection = "   • No levels calculated";
    }

    let pressureInfo = "";
    if (isMainTrend && result.pressure_zone) {
      pressureInfo = `\n   • **Golden Zone:** $${result.pressure_zone.lower_bound.toFixed(2)} - $${result.pressure_zone.upper_bound.toFixed(2)}`;
    }

    return `**${index + 1}. ${trendType} ${trend.type.toUpperCase()}** (${trend.period})
   • **Magnitude:** $${magnitude} move
   • **Range:** $${trend.low?.toFixed(2)} → $${trend.high?.toFixed(2)}
   • **Fibonacci Levels:**
${fibSection}${pressureInfo}`;
  })
  .join("\n\n")}
`;
  }

  return `## 📊 Fibonacci Analysis - ${result.symbol}

**Analysis Period:** ${result.start_date} to ${result.end_date} (${result.timeframe === "1h" ? "Hourly" : result.timeframe === "1d" ? "Daily" : result.timeframe === "1w" ? "Weekly" : result.timeframe === "1mo" ? "Monthly" : result.timeframe} timeframe)
**Current Price:** $${result.current_price.toFixed(2)}
**Trend Direction:** ${result.market_structure.trend_direction}
**Confidence Score:** ${(result.confidence_score * 100).toFixed(1)}%
${bigThreeSection}
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

### Top Performing Sectors:
${topSectors.map(([sector, perf]) => `• **${sector}**: ${perf > 0 ? "+" : ""}${perf.toFixed(2)}%`).join("\n")}

### Underperforming Sectors:
${bottomSectors.map(([sector, perf]) => `• **${sector}**: ${perf.toFixed(2)}%`).join("\n")}

### Market Outlook:
${result.market_outlook}

### Key Factors:
${result.key_factors.map((factor) => `• ${factor}`).join("\n")}
`;
}

function formatFundamentalsResponse(result: StockFundamentalsResponse): string {
  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return `## Fundamental Analysis - ${result.symbol}
*Analysis Date: ${analysisDate}*

**Company:** ${result.company_name}
**Current Price:** $${result.current_price.toFixed(2)} (${result.price_change >= 0 ? "+" : ""}${result.price_change_percent.toFixed(2)}%)

### Valuation Metrics:
${result.pe_ratio ? `• **P/E Ratio:** ${result.pe_ratio.toFixed(2)}` : ""}
${result.pb_ratio ? `• **P/B Ratio:** ${result.pb_ratio.toFixed(2)}` : ""}
${result.dividend_yield ? `• **Dividend Yield:** ${result.dividend_yield.toFixed(2)}%` : ""}

### Financial Health:
• **Market Cap:** $${(result.market_cap / 1e9).toFixed(2)}B
• **Volume:** ${result.volume.toLocaleString()} (Avg: ${result.avg_volume.toLocaleString()})
${result.beta ? `• **Beta:** ${result.beta.toFixed(2)} (volatility vs market)` : ""}

### Price Range:
• **52-Week High:** $${result.fifty_two_week_high.toFixed(2)}
• **52-Week Low:** $${result.fifty_two_week_low.toFixed(2)}
`;
}

function formatStochasticResponse(result: StochasticAnalysisResponse): string {
  const signalEmoji =
    result.current_signal === "overbought"
      ? "📈"
      : result.current_signal === "oversold"
        ? "📉"
        : "➡️";

  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const recentSignals = result.signal_changes.slice(-3);

  return `## ${signalEmoji} Stochastic Oscillator Analysis - ${result.symbol}
*Analysis Date: ${analysisDate}*

**Analysis Period:** ${result.start_date || "Dynamic"} to ${result.end_date || "Current"} (${result.timeframe} timeframe)
**Current Price:** $${result.current_price.toFixed(2)}
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

// Chat hook - streams LLM responses in real-time
export const useAnalysis = (
  currentSymbol: string | null,
  selectedDateRange: { start: string; end: string },
  setMessages: (updater: (prevMessages: any[]) => any[]) => void,
  setSelectedDateRange: (range: { start: string; end: string }) => void,
  selectedInterval?: string,
  sessionId?: string | null,
  setSessionId?: (id: string) => void,
) => {
  return useMutation({
    mutationKey: ["chat", sessionId],
    mutationFn: async (userMessage: string) => {
      // Add user message immediately
      const userMessageObj = {
        role: "user" as const,
        content: userMessage,
        timestamp: new Date().toISOString(),
      };

      // Create placeholder for streaming assistant message
      const assistantMessageId = Date.now();
      const assistantMessageObj = {
        role: "assistant" as const,
        content: "",
        timestamp: new Date().toISOString(),
        _id: assistantMessageId,
      };

      setMessages((prev) => [...prev, userMessageObj, assistantMessageObj]);

      // Stream response (returns cleanup function)
      return new Promise((resolve, reject) => {
        const cleanup = chatService.sendMessageStream(
          userMessage,
          sessionId || null,
          (chunk: string) => {
            // Use flushSync to force immediate render of each chunk
            flushSync(() => {
              setMessages((prev) =>
                prev.map((msg: any) =>
                  msg._id === assistantMessageId
                    ? { ...msg, content: msg.content + chunk }
                    : msg,
                ),
              );
            });
            // Force browser to repaint by reading layout (this triggers reflow)
            document.body.offsetHeight;
          },
          (newSessionId: string) => {
            // Session created callback
            if (setSessionId) {
              setSessionId(newSessionId);
            }
          },
          (finalSessionId: string, messageCount: number) => {
            // Stream complete

            // Resolve the promise with final content
            setMessages((prev) => {
              const msg = prev.find((m: any) => m._id === assistantMessageId);
              resolve({ type: "chat", content: msg?.content || "" });
              return prev;
            });
          },
          (error: string) => {
            // Error callback
            console.error("❌ Streaming error:", error);
            setMessages((prev) =>
              prev.map((msg: any) =>
                msg._id === assistantMessageId
                  ? {
                      ...msg,
                      content: `❌ **Error**: ${error}`,
                    }
                  : msg,
              ),
            );
            reject(new Error(error));
          },
        );
      });
    },
  });
};

// Button analysis hook - direct API calls
export const useButtonAnalysis = (
  currentSymbol: string | null,
  selectedDateRange: { start: string; end: string },
  setMessages: (updater: (prevMessages: any[]) => any[]) => void,
  setSelectedDateRange: (range: { start: string; end: string }) => void,
  selectedInterval?: string,
  sessionId?: string | null,
  setSessionId?: (id: string) => void,
) => {
  return useMutation({
    mutationKey: [
      "analysis",
      currentSymbol,
      selectedInterval,
      selectedDateRange.start,
      selectedDateRange.end,
    ],
    mutationFn: async (
      analysisType: "fibonacci" | "macro" | "fundamentals" | "stochastic",
    ) => {
      let response;
      let currentSessionId = sessionId;

      // Create session if it doesn't exist yet (fast, no LLM call)
      if (!currentSessionId) {
        console.log(
          "🆕 No session exists, creating one for algorithm results...",
        );
        try {
          const sessionResponse = await chatService.createSession();
          currentSessionId = sessionResponse.session_id;
          if (setSessionId) {
            setSessionId(currentSessionId);
          }
          console.log("✅ Session created:", currentSessionId);
        } catch (error) {
          console.error("❌ Failed to create session:", error);
          // Continue without session - results will still show but won't be in LLM context
        }
      }

      switch (analysisType) {
        case "fibonacci": {
          if (!currentSymbol)
            throw new Error("Please select a stock symbol first.");

          let startDate = selectedDateRange.start;
          let endDate = selectedDateRange.end;

          // Calculate dates if not set
          if (!startDate || !endDate) {
            const today = new Date();
            let periodsBack: Date;

            switch (selectedInterval) {
              case "1h":
                periodsBack = new Date(
                  today.getTime() - 30 * 24 * 60 * 60 * 1000,
                );
                break;
              case "1w":
                periodsBack = new Date(
                  today.getTime() - 365 * 24 * 60 * 60 * 1000,
                );
                break;
              case "1mo":
                periodsBack = new Date(
                  today.getTime() - 2 * 365 * 24 * 60 * 60 * 1000,
                );
                break;
              default:
                periodsBack = new Date(
                  today.getTime() - 6 * 30 * 24 * 60 * 60 * 1000,
                );
            }

            startDate = periodsBack.toISOString().split("T")[0];
            endDate = today.toISOString().split("T")[0];
          }

          const result = await analysisService.fibonacciAnalysis({
            symbol: currentSymbol,
            start_date: startDate,
            end_date: endDate,
            timeframe: selectedInterval || "1d",
          });
          response = {
            type: "fibonacci",
            content: formatFibonacciResponse(result),
            analysis_data: result,
          };
          break;
        }

        case "macro": {
          const result = await analysisService.macroSentimentAnalysis({});
          response = { type: "macro", content: formatMacroResponse(result) };
          break;
        }

        case "fundamentals": {
          if (!currentSymbol)
            throw new Error("Please select a stock symbol first.");
          const result = await analysisService.stockFundamentals({
            symbol: currentSymbol,
          });
          response = {
            type: "fundamentals",
            content: formatFundamentalsResponse(result),
          };
          break;
        }

        case "stochastic": {
          if (!currentSymbol)
            throw new Error("Please select a stock symbol first.");

          let startDate = selectedDateRange.start;
          let endDate = selectedDateRange.end;

          if (!startDate || !endDate) {
            const today = new Date();
            let periodsBack: Date;

            switch (selectedInterval) {
              case "1h":
                periodsBack = new Date(
                  today.getTime() - 30 * 24 * 60 * 60 * 1000,
                );
                break;
              case "1w":
                periodsBack = new Date(
                  today.getTime() - 365 * 24 * 60 * 60 * 1000,
                );
                break;
              case "1mo":
                periodsBack = new Date(
                  today.getTime() - 2 * 365 * 24 * 60 * 60 * 1000,
                );
                break;
              default:
                periodsBack = new Date(
                  today.getTime() - 6 * 30 * 24 * 60 * 60 * 1000,
                );
            }

            startDate = periodsBack.toISOString().split("T")[0];
            endDate = today.toISOString().split("T")[0];
          }

          const result = await analysisService.stochasticAnalysis({
            symbol: currentSymbol,
            start_date: startDate,
            end_date: endDate,
            timeframe: (selectedInterval as "1h" | "1d" | "1w" | "1mo") || "1d",
            k_period: 14,
            d_period: 3,
          });
          response = {
            type: "stochastic",
            content: formatStochasticResponse(result),
            analysis_data: result,
          };
          break;
        }
      }

      // Sync to backend session BEFORE returning (inside mutationFn)
      console.log("🔍 Checking session for context sync:", {
        currentSessionId,
        hasResponse: !!response,
        responseType: response?.type,
        contentLength: response?.content?.length,
      });

      if (currentSessionId && response) {
        try {
          console.log(
            "📤 Sending context to backend session:",
            currentSessionId,
          );
          await chatService.addContextToSession(
            currentSessionId,
            response.content,
          );
          console.log(
            "✅ Context synced to backend session:",
            currentSessionId,
          );
        } catch (error) {
          console.error("❌ Failed to sync context to backend:", error);
          // Non-critical error - continue anyway
        }
      } else {
        console.warn("⚠️ Skipping context sync:", {
          reason: !currentSessionId ? "No session ID" : "No response",
          currentSessionId,
          response: !!response,
        });
      }

      return response;
    },
    onSuccess: (response) => {
      // Add to frontend messages
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
};
