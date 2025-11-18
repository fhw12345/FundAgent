/**
 * Feedback Leaderboard Component
 * Displays a list of feedback items (features or bugs) sorted by votes.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { FeedbackType } from "../../types/feedback";
import { feedbackApi } from "../../services/feedbackApi";
import { FeedbackListItem } from "./FeedbackListItem";

interface FeedbackLeaderboardProps {
  type: FeedbackType;
  onItemClick: (itemId: string) => void;
}

export function FeedbackLeaderboard({
  type,
  onItemClick,
}: FeedbackLeaderboardProps) {
  const { t } = useTranslation(["feedback", "common"]);
  const {
    data: items,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["feedback", type],
    queryFn: () => feedbackApi.listItems(type),
    refetchInterval: 30000, // Refresh every 30 seconds
  });

  const title =
    type === "feature"
      ? t("feedback:leaderboard.featureRequests")
      : t("feedback:leaderboard.bugReports");
  const icon = type === "feature" ? "✨" : "🐛";

  return (
    <div className="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg border border-gray-200/50 p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <span>{icon}</span>
          <span>{title}</span>
        </h2>
        <p className="mt-1 text-sm text-gray-600">
          {type === "feature"
            ? t("feedback:leaderboard.featureDescription")
            : t("feedback:leaderboard.bugDescription")}
        </p>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="py-8 px-4 bg-red-50 border border-red-200 rounded-xl">
          <p className="text-red-700 text-center">
            {t("feedback:leaderboard.loadFailed")}
          </p>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && items && items.length === 0 && (
        <div className="py-12 text-center">
          <div className="text-6xl mb-4">{icon}</div>
          <p className="text-gray-600">
            {type === "feature"
              ? t("feedback:leaderboard.noFeatureRequests")
              : t("feedback:leaderboard.noBugReports")}
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {t("feedback:leaderboard.beFirst")}
          </p>
        </div>
      )}

      {/* List of Items */}
      {!isLoading && !error && items && items.length > 0 && (
        <div className="space-y-3">
          {items.map((item, index) => (
            <FeedbackListItem
              key={item.item_id}
              item={item}
              onItemClick={onItemClick}
              rank={index + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
