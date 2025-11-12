/**
 * Watchlist API service.
 * Manages watched stock symbols for automated analysis.
 */

import { WatchlistItem, WatchlistItemCreate } from "../types/watchlist";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Get all watchlist items for the user.
 */
export async function getWatchlist(): Promise<WatchlistItem[]> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch watchlist: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Add a symbol to the watchlist.
 */
export async function addToWatchlist(
  item: WatchlistItemCreate
): Promise<WatchlistItem> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(item),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to add to watchlist: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Remove a symbol from the watchlist.
 */
export async function removeFromWatchlist(watchlistId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/${watchlistId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to remove from watchlist: ${response.statusText}`);
  }
}

/**
 * Manually trigger analysis for all watchlist symbols.
 */
export async function triggerWatchlistAnalysis(): Promise<{ status: string; message: string }> {
  const response = await fetch(`${API_BASE_URL}/api/watchlist/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || `Failed to trigger analysis: ${response.statusText}`);
  }

  return response.json();
}
