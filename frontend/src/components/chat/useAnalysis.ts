/**
 * useAnalysis Hook
 *
 * SIMPLIFIED VERSION:
 * - User chat messages → LLM (no pattern matching)
 * - Button clicks → Direct analysis endpoints
 */

import { flushSync } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { analysisService } from "../../services/analysis";
import { chatService } from "../../services/api";
import { chatKeys } from "../../hooks/useChats";
import { useOptimisticCreditDeduction, creditKeys } from "../../hooks/useCredits";
import {
  formatFibonacciResponse,
  formatMacroResponse,
  formatFundamentalsResponse,
  formatStochasticResponse,
} from "./analysisFormatters";
import { calculateDateRange } from "../../utils/dateRangeCalculator";
import {
  extractFibonacciMetadata,
  extractStochasticMetadata,
} from "../../utils/analysisMetadataExtractor";

// Formatting functions moved to analysisFormatters.ts

// Chat hook - streams LLM responses in real-time
export const useAnalysis = (
  _currentSymbol: string | null,
  _selectedDateRange: { start: string; end: string },
  setMessages: (updater: (prevMessages: any[]) => any[]) => void,
  _setSelectedDateRange: (range: { start: string; end: string }) => void,
  _selectedInterval?: string,
  chatId?: string | null,
  setChatId?: (id: string) => void,
  modelSettings?: { model: string; thinking_enabled: boolean; max_tokens: number },
) => {
  const queryClient = useQueryClient();
  const optimisticDeduction = useOptimisticCreditDeduction();

  return useMutation({
    mutationKey: ["chat", chatId],
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

      // Optimistically deduct credits (10 credits estimated cost)
      const { rollback } = optimisticDeduction.deduct(10.0);

      // Local accumulator to avoid race conditions
      let accumulatedContent = "";

      // Stream response using persistent MongoDB endpoint
      return new Promise((resolve, reject) => {
        chatService.sendMessageStreamPersistent(
          userMessage,
          chatId || null,
          (chunk: string) => {
            // Accumulate content locally (SAFE - no race condition)
            accumulatedContent += chunk;

            // Use flushSync to force immediate render of each chunk
            flushSync(() => {
              setMessages((prev) =>
                prev.map((msg: any) =>
                  msg._id === assistantMessageId
                    ? { ...msg, content: accumulatedContent }
                    : msg,
                ),
              );
            });
          },
          (newChatId: string) => {
            // Chat created callback - save new chat ID
            if (setChatId) {
              setChatId(newChatId);
            }
            // Don't invalidate here - wait for stream completion to avoid duplicate requests
          },
          (title: string) => {
            // Title generated callback - could update UI if needed
            console.log("📝 Chat title generated:", title);
          },
          () => {
            // Stream complete - use accumulated content (SAFE)
            resolve({ type: "chat", content: accumulatedContent });
            // Invalidate chat list ONCE after stream completes
            void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
            // Refresh credits to show actual cost deducted by backend
            void queryClient.invalidateQueries({ queryKey: creditKeys.profile() });
          },
          (error: string) => {
            // Error callback - rollback optimistic deduction
            console.error("❌ Streaming error:", error);
            rollback();
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
          // LLM Configuration options
          modelSettings ? {
            model: modelSettings.model,
            thinking_enabled: modelSettings.thinking_enabled,
            max_tokens: modelSettings.max_tokens,
            debug_enabled: modelSettings.debug_enabled,
          } : undefined,
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
  _setSelectedDateRange: (range: { start: string; end: string }) => void,
  selectedInterval?: string,
  chatId?: string | null,
  setChatId?: (id: string) => void,
) => {
  const queryClient = useQueryClient();

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

      // Title mapping for different analysis types
      const titleMap = {
        fibonacci: "Fibonacci Analysis",
        macro: "Macro Sentiment",
        fundamentals: "Stock Fundamentals",
        stochastic: "Stochastic Analysis",
      };

      const analysisTitle = titleMap[analysisType];
      const chatTitle = currentSymbol
        ? `${currentSymbol} ${analysisTitle}`
        : analysisTitle;

      // Source matches analysis type for MongoDB filtering
      const sourceType = "tool"; // All analysis types use 'tool' source

      switch (analysisType) {
        case "fibonacci": {
          if (!currentSymbol)
            throw new Error("Please select a stock symbol first.");

          // Calculate date range using shared utility
          const dateRange = calculateDateRange(
            selectedDateRange,
            (selectedInterval as "1h" | "1d" | "1w" | "1mo") || "1d",
          );

          const result = await analysisService.fibonacciAnalysis({
            symbol: currentSymbol,
            start_date: dateRange.start,
            end_date: dateRange.end,
            timeframe: (selectedInterval || "1d") as "1h" | "1d" | "1w" | "1mo",
          });
          response = {
            type: "fibonacci",
            content: formatFibonacciResponse(result),
            // Store only compact metadata, not full price history
            analysis_data: extractFibonacciMetadata(result),
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

          // Calculate date range using shared utility
          const dateRange = calculateDateRange(
            selectedDateRange,
            (selectedInterval as "1h" | "1d" | "1w" | "1mo") || "1d",
          );

          const result = await analysisService.stochasticAnalysis({
            symbol: currentSymbol,
            start_date: dateRange.start,
            end_date: dateRange.end,
            timeframe: (selectedInterval as "1h" | "1d" | "1w" | "1mo") || "1d",
            k_period: 14,
            d_period: 3,
          });
          response = {
            type: "stochastic",
            content: formatStochasticResponse(result),
            // Store only compact metadata, not full K/D arrays
            analysis_data: extractStochasticMetadata(result),
          };
          break;
        }
      }

      // Save to MongoDB using streaming endpoint (analysis sources skip LLM)
      if (response) {
        return new Promise((resolve, reject) => {
          chatService.sendMessageStreamPersistent(
            response.content,
            chatId || null,
            () => {
              // No chunks expected with analysis sources
            },
            (newChatId: string) => {
              // Chat created callback
              if (setChatId) {
                setChatId(newChatId);
              }
              // Don't invalidate here - wait for completion to avoid duplicate requests
            },
            () => {
              // No title generation with custom title
            },
            () => {
              // Done callback - invalidate chat list ONCE after completion
              resolve(response);
              void queryClient.invalidateQueries({
                queryKey: chatKeys.lists(),
              });
              // Refresh credits to show actual cost deducted by backend
              void queryClient.invalidateQueries({
                queryKey: creditKeys.profile(),
              });
            },
            (error: string) => {
              console.error("❌ Failed to save to MongoDB:", error);
              reject(new Error(error));
            },
            {
              title: chatTitle,
              role: "assistant",
              source: sourceType,
              // Wrap in raw_data to avoid schema mismatch
              metadata: { raw_data: response.analysis_data },
            },
          );
        });
      }

      return response;
    },
    onSuccess: (response: any) => {
      console.log("✅ Button analysis complete:", {
        type: response?.type,
        hasAnalysisData: !!response?.analysis_data,
        analysisData: response?.analysis_data,
      });

      // Add to frontend messages
      if (response) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: response.content,
            timestamp: new Date().toISOString(),
            analysis_data: response.analysis_data,
          },
        ]);

        console.log("📝 Message added to state with analysis_data");
      }
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
