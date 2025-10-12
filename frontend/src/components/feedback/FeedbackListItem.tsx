/**
 * Feedback List Item Component
 * Displays a single feedback item with voting and navigation to detail view.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { FeedbackItem } from "../../types/feedback";
import { feedbackApi } from "../../services/feedbackApi";
import { STATUS_LABELS, STATUS_COLORS } from "../../types/feedback";

interface FeedbackListItemProps {
  item: FeedbackItem;
  onItemClick: (itemId: string) => void;
  rank?: number; // Position in leaderboard (1st, 2nd, 3rd, etc.)
}

export function FeedbackListItem({
  item,
  onItemClick,
  rank,
}: FeedbackListItemProps) {
  const queryClient = useQueryClient();

  // Vote mutation with optimistic updates
  const voteMutation = useMutation({
    mutationFn: async () => {
      if (item.hasVoted) {
        await feedbackApi.unvoteItem(item.item_id);
      } else {
        await feedbackApi.voteItem(item.item_id);
      }
    },
    onMutate: async () => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["feedback", item.type] });

      // Snapshot previous value
      const previousItems = queryClient.getQueryData(["feedback", item.type]);

      // Optimistically update the cache
      queryClient.setQueryData(
        ["feedback", item.type],
        (old: FeedbackItem[] | undefined) => {
          if (!old) return old;
          return old.map((i) =>
            i.item_id === item.item_id
              ? {
                  ...i,
                  hasVoted: !i.hasVoted,
                  voteCount: i.hasVoted ? i.voteCount - 1 : i.voteCount + 1,
                }
              : i,
          );
        },
      );

      return { previousItems };
    },
    onError: (_err, _variables, context) => {
      // Rollback on error
      if (context?.previousItems) {
        queryClient.setQueryData(
          ["feedback", item.type],
          context.previousItems,
        );
      }
    },
    onSettled: () => {
      // Refetch to ensure sync with server
      queryClient.invalidateQueries({ queryKey: ["feedback", item.type] });
    },
  });

  const handleVote = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent navigation when clicking vote button
    voteMutation.mutate();
  };

  const handleItemClick = () => {
    onItemClick(item.item_id);
  };

  const statusConfig = STATUS_COLORS[item.status];

  // Ranking badge configuration
  const getRankBadge = () => {
    if (!rank) return null;

    const rankConfig: Record<
      number,
      { emoji: string; gradient: string; text: string; shine: string }
    > = {
      1: {
        emoji: "🏆",
        gradient: "from-yellow-400 via-yellow-500 to-amber-600",
        text: "1st",
        shine: "shadow-xl shadow-yellow-500/50",
      },
      2: {
        emoji: "🥈",
        gradient: "from-gray-300 via-gray-400 to-gray-500",
        text: "2nd",
        shine: "shadow-lg shadow-gray-400/50",
      },
      3: {
        emoji: "🥉",
        gradient: "from-orange-400 via-orange-500 to-orange-600",
        text: "3rd",
        shine: "shadow-lg shadow-orange-400/50",
      },
    };

    const config = rankConfig[rank];
    if (config) {
      return (
        <div
          className={`absolute -top-2 -left-2 flex items-center gap-1 px-3 py-1 rounded-full bg-gradient-to-r ${config.gradient} ${config.shine} text-white font-bold text-sm z-10 animate-pulse`}
        >
          <span className="text-lg">{config.emoji}</span>
          <span>{config.text}</span>
        </div>
      );
    }

    // Ranks 4+
    return (
      <div className="absolute -top-2 -left-2 flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-r from-blue-400 to-blue-600 text-white font-bold text-xs shadow-md z-10">
        #{rank}
      </div>
    );
  };

  return (
    <div
      className={`group relative p-4 bg-white rounded-xl border ${
        rank && rank <= 3
          ? "border-2 border-yellow-400 bg-gradient-to-br from-white to-yellow-50"
          : "border-gray-200"
      } hover:border-blue-300 hover:shadow-md transition-all duration-200 cursor-pointer`}
      onClick={handleItemClick}
    >
      {getRankBadge()}
      <div className="flex items-start gap-4">
        {/* Vote Button */}
        <div className="flex-shrink-0">
          <button
            onClick={handleVote}
            disabled={voteMutation.isPending}
            className={`flex flex-col items-center justify-center w-14 h-14 rounded-lg transition-all duration-200 ${
              item.hasVoted
                ? "bg-blue-500 text-white shadow-md hover:bg-blue-600"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            } ${voteMutation.isPending ? "opacity-50 cursor-wait" : ""}`}
          >
            <svg
              className="w-5 h-5"
              fill="currentColor"
              viewBox="0 0 20 20"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
            </svg>
            <span className="text-xs font-semibold mt-0.5">
              {item.voteCount}
            </span>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 mb-2">
            <h3 className="text-base font-semibold text-gray-900 group-hover:text-blue-600 transition-colors line-clamp-2">
              {item.title}
            </h3>
            <span
              className={`flex-shrink-0 inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium border ${statusConfig.bg} ${statusConfig.text} ${statusConfig.border}`}
            >
              {STATUS_LABELS[item.status]}
            </span>
          </div>

          <div className="flex items-center gap-4 text-sm text-gray-500">
            {/* Author */}
            <span className="flex items-center gap-1">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                />
              </svg>
              {item.authorUsername || "Unknown"}
            </span>

            {/* Comment Count */}
            <span className="flex items-center gap-1">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"
                />
              </svg>
              {item.commentCount}
            </span>

            {/* Created Date */}
            <span className="flex items-center gap-1">
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              {new Date(item.createdAt).toLocaleDateString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
