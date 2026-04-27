/**
 * useAnalysis Hook
 *
 * Streams LLM chat responses via the persistent MongoDB endpoint.
 * (Pre-rebrand button-driven analysis hooks were removed.)
 */

import { flushSync } from "react-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { chatService } from "../../services/api";
import { chatKeys } from "../../hooks/useChats";
import type { ModelSettings } from "../../types/models";
import type { DeepStreamEvent } from "../../types/api";
import i18n from "../../i18n";

// Chat hook - streams LLM responses in real-time
export const useAnalysis = (
  currentSymbol: string | null, // Used for symbol context injection (takes priority over DB)
  _selectedDateRange: { start: string; end: string },
  setMessages: (updater: (prevMessages: any[]) => any[]) => void,
  _setSelectedDateRange: (range: { start: string; end: string }) => void,
  _selectedInterval?: string,
  chatId?: string | null,
  setChatId?: (id: string) => void,
  modelSettings?: ModelSettings,
  agentMode?: "v2" | "v3" | "v4-deep",
  onDeepEvent?: (event: DeepStreamEvent) => void,
) => {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationKey: ["chat", chatId],
    mutationFn: async (userMessage: string) => {
      // Input validation
      const trimmed = userMessage.trim();

      if (!trimmed) {
        throw new Error("Message cannot be empty");
      }

      if (trimmed.length > 5000) {
        throw new Error("Message too long. Maximum 5000 characters allowed.");
      }

      // Check for potential XSS patterns (additional safety layer)
      if (/<script|javascript:|onerror=/i.test(trimmed)) {
        throw new Error("Invalid characters detected in message");
      }

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
          },
          (title: string) => {
            console.log("📝 Chat title generated:", title);
          },
          () => {
            // Stream complete
            resolve({ type: "chat", content: accumulatedContent });
            void queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
          },
          (error: string) => {
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
          // Tool event callbacks (agent mode v3 only)
          (event) => {
            const toolProgressMessage = {
              role: "assistant" as const,
              content: "",
              timestamp: new Date().toISOString(),
              _id: `tool_${event.run_id}`,
              tool_progress: {
                toolName: event.tool_name,
                displayName: event.display_name,
                icon: event.icon,
                status: "running" as const,
                symbol: event.symbol,
                inputs: event.inputs,
              },
            };

            setMessages((prev) => {
              const placeholder = prev.find(msg => msg._id === assistantMessageId);
              const withoutPlaceholder = prev.filter(msg => msg._id !== assistantMessageId);
              return [...withoutPlaceholder, toolProgressMessage, placeholder || assistantMessageObj];
            });
          },
          (event) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg._id === `tool_${event.run_id}` && msg.tool_progress
                  ? {
                      ...msg,
                      tool_progress: {
                        ...msg.tool_progress,
                        status: "success" as const,
                        output: event.output,
                        durationMs: event.duration_ms,
                      },
                    }
                  : msg,
              ),
            );
          },
          (event) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg._id === `tool_${event.run_id}` && msg.tool_progress
                  ? {
                      ...msg,
                      tool_progress: {
                        ...msg.tool_progress,
                        status: "error" as const,
                        error: event.error,
                        durationMs: event.duration_ms,
                      },
                    }
                  : msg,
              ),
            );
          },
          // Deep agent event callback (v4-deep only)
          onDeepEvent,
          {
            model: modelSettings?.model ?? "qwen-plus",
            thinking_enabled: modelSettings?.thinking_enabled ?? false,
            max_tokens: modelSettings?.max_tokens ?? 3000,
            debug_enabled: modelSettings?.debug_enabled ?? false,
            agent_version: agentMode,
            language: (i18n.language === "zh-CN" || i18n.language === "en" ? i18n.language : "zh-CN") as "zh-CN" | "en",
            current_symbol: currentSymbol || undefined,
          },
        );
      });
    },
  });

  return mutation;
};
