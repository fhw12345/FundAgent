/**
 * Watchlist panel for managing tracked stock symbols.
 * Allows users to add/remove symbols for automated monitoring.
 * Shows last analysis time and countdown to next 5-minute analysis cycle.
 */

import { useState } from "react";
import {
  useWatchlist,
  useAddToWatchlist,
  useRemoveFromWatchlist,
  useTriggerWatchlistAnalysis,
} from "../../hooks/useWatchlist";

// Helper to format time ago
function formatTimeAgo(date: Date): string {
  const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// Calculate next analysis time (next 5-minute mark)
function getNextAnalysisTime(): Date {
  const now = new Date();
  const minutes = now.getMinutes();
  const nextMinute = Math.ceil((minutes + 1) / 5) * 5;
  const next = new Date(now);
  next.setMinutes(nextMinute, 0, 0);
  return next;
}

// Format countdown to next analysis
function formatCountdown(targetDate: Date): string {
  const seconds = Math.floor((targetDate.getTime() - new Date().getTime()) / 1000);
  if (seconds <= 0) return "Analyzing now...";
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
}

export function WatchlistPanel() {
  const [newSymbol, setNewSymbol] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: watchlist, isLoading } = useWatchlist();
  const addMutation = useAddToWatchlist();
  const removeMutation = useRemoveFromWatchlist();
  const triggerAnalysisMutation = useTriggerWatchlistAnalysis();

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const symbol = newSymbol.trim().toUpperCase();

    if (!symbol) {
      setError("Please enter a stock symbol");
      return;
    }

    try {
      await addMutation.mutateAsync({ symbol });
      setNewSymbol("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add symbol");
    }
  };

  const handleRemove = async (watchlistId: string) => {
    try {
      await removeMutation.mutateAsync(watchlistId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove symbol");
    }
  };

  const handleTriggerAnalysis = async () => {
    try {
      await triggerAnalysisMutation.mutateAsync();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to trigger analysis");
    }
  };

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Watchlist</h2>
        <button
          onClick={handleTriggerAnalysis}
          disabled={triggerAnalysisMutation.isPending || !watchlist || watchlist.length === 0}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {triggerAnalysisMutation.isPending ? "Analyzing..." : "Analyze Now"}
        </button>
      </div>

      {/* Add Symbol Form */}
      <form onSubmit={handleAdd} className="mb-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={newSymbol}
            onChange={(e) => setNewSymbol(e.target.value)}
            placeholder="Enter symbol (e.g., AAPL)"
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={addMutation.isPending}
          />
          <button
            type="submit"
            disabled={addMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {addMutation.isPending ? "Adding..." : "Add"}
          </button>
        </div>
        {error && (
          <p className="mt-2 text-sm text-red-600">{error}</p>
        )}
      </form>

      {/* Watchlist Items */}
      {isLoading ? (
        <div className="text-center py-4 text-gray-500">Loading...</div>
      ) : watchlist && watchlist.length > 0 ? (
        <div className="space-y-2">
          {watchlist.map((item) => (
            <div
              key={item.watchlist_id}
              className="flex items-center justify-between p-3 bg-gray-50 rounded-md hover:bg-gray-100"
            >
              <div className="flex-1">
                <div className="font-medium text-gray-900">{item.symbol}</div>
                {item.notes && (
                  <div className="text-sm text-gray-500">{item.notes}</div>
                )}
                <div className="text-xs text-gray-400 mt-1">
                  Added: {new Date(item.added_at).toLocaleDateString()}
                  {item.last_analyzed_at && (
                    <span className="ml-2">
                      • Last analyzed: {formatTimeAgo(new Date(item.last_analyzed_at))}
                    </span>
                  )}
                  {!item.last_analyzed_at && (
                    <span className="ml-2 text-amber-600">
                      • Waiting for first analysis
                    </span>
                  )}
                </div>
              </div>
              <button
                onClick={() => handleRemove(item.watchlist_id)}
                disabled={removeMutation.isPending}
                className="ml-4 px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded-md disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-500">
          <p>No symbols in watchlist</p>
          <p className="text-sm mt-1">Add symbols to track their performance</p>
        </div>
      )}
    </div>
  );
}
