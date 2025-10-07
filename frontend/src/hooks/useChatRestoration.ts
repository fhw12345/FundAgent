/**
 * Hook for restoring chat state when selecting a previous conversation.
 * Loads messages from MongoDB and restores UI state (symbol, interval, overlays).
 */

import { useCallback } from "react";
import { useChatDetail } from "./useChats";
import type { ChatMessage } from "../types/api";
import type { TimeInterval } from "../services/market";

interface ChatRestoreCallbacks {
  setMessages: (messages: ChatMessage[]) => void;
  setCurrentSymbol: (symbol: string) => void;
  setCurrentCompanyName: (name: string) => void;
  setSelectedInterval: (interval: TimeInterval) => void;
  setSelectedDateRange: (range: { start: string; end: string }) => void;
  setChatId: (chatId: string | null) => void;
}

export function useChatRestoration(callbacks: ChatRestoreCallbacks) {
  const {
    setMessages,
    setCurrentSymbol,
    setCurrentCompanyName,
    setSelectedInterval,
    setSelectedDateRange,
    setChatId,
  } = callbacks;

  /**
   * Load chat and restore full UI state
   */
  const restoreChat = useCallback(
    async (chatId: string) => {
      try {
        // Import chatService dynamically to avoid circular deps
        const { chatService } = await import("../services/api");

        // Fetch chat detail with messages
        const chatDetail = await chatService.getChatDetail(chatId);

        // Convert backend Message[] to frontend ChatMessage[]
        const restoredMessages: ChatMessage[] = chatDetail.messages.map(
          (msg) => ({
            role: msg.role as "user" | "assistant",
            content: msg.content,
            timestamp: msg.timestamp,
            // Unwrap from raw_data field
            analysis_data: msg.metadata?.raw_data || msg.metadata,
          }),
        );

        // Restore messages
        setMessages(restoredMessages);

        // Restore UI state from chat.ui_state
        const uiState = chatDetail.chat.ui_state;

        console.log("🔄 Restoring chat UI state:", {
          chatId,
          symbol: uiState.current_symbol,
          interval: uiState.current_interval,
          dateRange: uiState.current_date_range,
          overlays: uiState.active_overlays,
        });

        // Always set symbol (even if empty) to clear old state
        setCurrentSymbol(uiState.current_symbol || "");
        setCurrentCompanyName(uiState.current_symbol || "");

        console.log(
          "✅ Symbol restored to search bar:",
          uiState.current_symbol,
        );

        // Always set interval with fallback
        setSelectedInterval((uiState.current_interval as TimeInterval) || "1d");

        if (
          uiState.current_date_range?.start &&
          uiState.current_date_range?.end
        ) {
          setSelectedDateRange({
            start: uiState.current_date_range.start,
            end: uiState.current_date_range.end,
          });
        } else {
          setSelectedDateRange({ start: "", end: "" });
        }

        // TODO: Restore active_overlays when overlay state management is implemented

        // Set active chat for API calls
        setChatId(chatId);

        console.log("✅ Chat restored:", {
          chatId,
          messageCount: restoredMessages.length,
          symbol: uiState.current_symbol,
          interval: uiState.current_interval,
        });
      } catch (error) {
        console.error("❌ Failed to restore chat:", error);
        // On error, don't change current state
      }
    },
    [
      setMessages,
      setCurrentSymbol,
      setCurrentCompanyName,
      setSelectedInterval,
      setSelectedDateRange,
      setChatId,
    ],
  );

  return { restoreChat };
}
