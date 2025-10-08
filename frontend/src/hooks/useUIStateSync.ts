/**
 * Hook for debounced UI state synchronization to MongoDB.
 * Automatically saves chart state (symbol, interval, overlays) after user interaction.
 */

import { useEffect, useRef } from "react";
import { useUpdateUIState } from "./useChats";
import type { TimeInterval } from "../services/market";
import type { UIState } from "../types/api";

interface UIStateSyncProps {
  activeChatId: string | null;
  currentSymbol: string;
  selectedInterval: TimeInterval;
  selectedDateRange: { start: string; end: string };
  // TODO: Add active overlays when implemented
}

const DEBOUNCE_DELAY_MS = 2000; // 2 seconds

export function useUIStateSync(props: UIStateSyncProps) {
  const { activeChatId, currentSymbol, selectedInterval, selectedDateRange } =
    props;

  const updateMutation = useUpdateUIState();
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastChatIdRef = useRef<string | null>(null);
  const isFirstRenderAfterChatChange = useRef(false);

  useEffect(() => {
    // Skip if no active chat (new chat scenario)
    if (!activeChatId) {
      return;
    }

    // Detect chat change (restoration)
    if (lastChatIdRef.current !== activeChatId) {
      lastChatIdRef.current = activeChatId;
      isFirstRenderAfterChatChange.current = true;
      console.log("🔄 Chat changed, skipping initial sync");
      return; // Skip sync on first render after chat change
    }

    // Reset flag after first render
    if (isFirstRenderAfterChatChange.current) {
      isFirstRenderAfterChatChange.current = false;
    }

    // Clear existing timer
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Set new timer to sync after debounce delay
    debounceTimerRef.current = setTimeout(() => {
      const uiState: UIState = {
        current_symbol: currentSymbol || null,
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
    selectedInterval,
    selectedDateRange.start,
    selectedDateRange.end,
    // Note: updateMutation.mutate is stable, no need to include
  ]);

  return {
    isSyncing: updateMutation.isPending,
    syncError: updateMutation.error,
  };
}
