/**
 * Hook for debounced UI state synchronization to MongoDB.
 * Automatically saves chart state (symbol, interval, overlays) after user interaction.
 */

import { useEffect, useRef, useCallback } from "react";
import { useUpdateUIState } from "./useChats";
import type { TimeInterval } from "../services/market";
import type { UIState } from "../types/api";

interface UIStateSyncProps {
  activeChatId: string | null;
  currentSymbol: string;
  currentCompanyName: string;
  selectedInterval: TimeInterval;
  selectedDateRange: { start: string; end: string };
  // TODO: Add active overlays when implemented
}

const DEBOUNCE_DELAY_MS = 2000; // 2 seconds

export function useUIStateSync(props: UIStateSyncProps) {
  const { activeChatId, currentSymbol, currentCompanyName, selectedInterval, selectedDateRange } =
    props;

  const updateMutation = useUpdateUIState();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastChatIdRef = useRef<string | null>(null);
  const isFirstRenderAfterChatChange = useRef(false);

  // Store previous state values to save them when switching chats
  const prevStateRef = useRef<{
    symbol: string;
    companyName: string;
    interval: TimeInterval;
    dateRange: { start: string; end: string };
  }>({
    symbol: currentSymbol,
    companyName: currentCompanyName,
    interval: selectedInterval,
    dateRange: selectedDateRange,
  });

  // Expose flush function to manually trigger save (e.g., before sending message)
  const flushUIState = useCallback(() => {
    if (!activeChatId) return;

    // Clear any pending timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    // Save current state immediately
    const uiState: UIState = {
      current_symbol: currentSymbol || null,
      current_company_name: currentCompanyName || null,
      current_interval: selectedInterval,
      current_date_range: {
        start: selectedDateRange.start || null,
        end: selectedDateRange.end || null,
      },
      active_overlays: {},
    };

    // Only save if there's meaningful state
    if (currentSymbol || selectedDateRange.start) {
      updateMutation.mutate({
        chatId: activeChatId,
        uiState: { ui_state: uiState },
      });
      console.log("💾 UI state flushed immediately:", {
        chatId: activeChatId,
        symbol: currentSymbol,
        companyName: currentCompanyName,
      });
    }
  }, [activeChatId, currentSymbol, currentCompanyName, selectedInterval, selectedDateRange, updateMutation]);

  useEffect(() => {
    // Skip if no active chat (new chat scenario)
    if (!activeChatId) {
      return;
    }

    // Detect chat change (restoration)
    if (lastChatIdRef.current !== activeChatId) {
      // IMPORTANT: ALWAYS flush previous chat's state before switching (even if no pending timer)
      if (lastChatIdRef.current) {
        // Clear any pending timer
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }

        // Immediately save the PREVIOUS chat's state (from prevStateRef, not current props!)
        const uiState: UIState = {
          current_symbol: prevStateRef.current.symbol || null,
          current_company_name: prevStateRef.current.companyName || null,
          current_interval: prevStateRef.current.interval,
          current_date_range: {
            start: prevStateRef.current.dateRange.start || null,
            end: prevStateRef.current.dateRange.end || null,
          },
          active_overlays: {},
        };

        // Save if there's meaningful state (symbol or custom date range)
        if (prevStateRef.current.symbol || prevStateRef.current.dateRange.start) {
          updateMutation.mutate({
            chatId: lastChatIdRef.current,
            uiState: { ui_state: uiState },
          });
          console.log("💾 Flushed UI state before chat switch:", {
            chatId: lastChatIdRef.current,
            symbol: prevStateRef.current.symbol,
            companyName: prevStateRef.current.companyName,
          });
        } else {
          console.log("⏭️ Skipped flush (no symbol to save):", {
            chatId: lastChatIdRef.current,
            prevSymbol: prevStateRef.current.symbol,
          });
        }
      }

      lastChatIdRef.current = activeChatId;
      isFirstRenderAfterChatChange.current = true;
      console.log("🔄 Chat changed, skipping initial sync");
      return; // Skip sync on first render after chat change
    }

    // Reset flag after first render
    if (isFirstRenderAfterChatChange.current) {
      isFirstRenderAfterChatChange.current = false;
    }

    // Update prevStateRef with current values (for next chat switch)
    prevStateRef.current = {
      symbol: currentSymbol,
      companyName: currentCompanyName,
      interval: selectedInterval,
      dateRange: selectedDateRange,
    };

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer to sync after debounce delay
    debounceTimerRef.current = setTimeout(() => {
      const uiState: UIState = {
        current_symbol: currentSymbol || null,
        current_company_name: currentCompanyName || null,
        current_interval: selectedInterval,
        current_date_range: {
          start: selectedDateRange.start || null,
          end: selectedDateRange.end || null,
        },
        active_overlays: {}, // TODO: Add when overlay state is implemented
      };

      // Only sync if there's meaningful state to save
      if (currentSymbol || selectedDateRange.start) {
        updateMutation.mutate({
          chatId: activeChatId,
          uiState: { ui_state: uiState },
        });

        console.log("💾 UI state synced to MongoDB:", {
          chatId: activeChatId,
          symbol: currentSymbol,
          interval: selectedInterval,
        });
      }
    }, DEBOUNCE_DELAY_MS);

    // Cleanup on unmount
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    activeChatId,
    currentSymbol,
    currentCompanyName,
    selectedInterval,
    selectedDateRange.start,
    selectedDateRange.end,
    // Note: updateMutation.mutate is stable, no need to include
  ]);

  return {
    isSyncing: updateMutation.isPending,
    syncError: updateMutation.error,
    flushUIState,
  };
}
