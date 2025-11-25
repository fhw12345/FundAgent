/**
 * Watchlist API service.
 * Manages watched stock symbols for automated analysis.
 */

import { apiClient } from "./api";
import { WatchlistItem, WatchlistItemCreate } from "../types/watchlist";

/**
 * Get all watchlist items for the user.
 */
export async function getWatchlist(): Promise<WatchlistItem[]> {
  const response = await apiClient.get<WatchlistItem[]>("/api/watchlist");
  return response.data;
}

/**
 * Add a symbol to the watchlist.
 */
export async function addToWatchlist(
  item: WatchlistItemCreate
): Promise<WatchlistItem> {
  const response = await apiClient.post<WatchlistItem>("/api/watchlist", item);
  return response.data;
}

/**
 * Remove a symbol from the watchlist.
 */
export async function removeFromWatchlist(watchlistId: string): Promise<void> {
  await apiClient.delete(`/api/watchlist/${watchlistId}`);
}

/**
 * Manually trigger complete portfolio analysis (holdings + watchlist + market movers).
 * Uses the same endpoint as the CronJob for consistency.
 */
export async function triggerWatchlistAnalysis(): Promise<{
  status: string;
  run_id: string;
  message: string;
  note?: string;
}> {
  const response = await apiClient.post<{
    status: string;
    run_id: string;
    message: string;
    note?: string;
  }>(
    "/api/admin/portfolio/trigger-analysis"
  );
  return response.data;
}
