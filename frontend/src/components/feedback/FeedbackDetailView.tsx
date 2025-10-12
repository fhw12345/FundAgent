/**
 * Feedback Detail View Component
 * Shows full details of a feedback item with comments.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { FeedbackItem, FeedbackStatus } from "../../types/feedback";
import { feedbackApi } from "../../services/feedbackApi";
import { STATUS_LABELS, STATUS_COLORS } from "../../types/feedback";
import { authStorage } from "../../services/authService";

interface FeedbackDetailViewProps {
  itemId: string;
  onClose: () => void;
}

export function FeedbackDetailView({
  itemId,
  onClose,
}: FeedbackDetailViewProps) {
  const [commentContent, setCommentContent] = useState("");
  const [commentError, setCommentError] = useState("");
  const queryClient = useQueryClient();

  // Check if current user is admin
  const currentUser = authStorage.getUser();
  const isAdmin = currentUser?.is_admin || false;

  // Fetch item details
  const {
    data: item,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["feedback-item", itemId],
    queryFn: () => feedbackApi.getItem(itemId),
  });

  // Fetch comments
  const { data: comments = [] } = useQuery({
    queryKey: ["feedback-comments", itemId],
    queryFn: () => feedbackApi.getComments(itemId),
    enabled: !!item, // Only fetch comments if item loaded
  });

  // Vote mutation
  const voteMutation = useMutation({
    mutationFn: async () => {
      if (item?.hasVoted) {
        await feedbackApi.unvoteItem(itemId);
      } else {
        await feedbackApi.voteItem(itemId);
      }
    },
    onSuccess: () => {
      // Invalidate both detail view and list
      queryClient.invalidateQueries({ queryKey: ["feedback-item", itemId] });
      queryClient.invalidateQueries({ queryKey: ["feedback"] });
    },
  });

  // Comment mutation
  const commentMutation = useMutation({
    mutationFn: (content: string) => feedbackApi.addComment(itemId, content),
    onSuccess: () => {
      // Clear form and refetch
      setCommentContent("");
      setCommentError("");
      queryClient.invalidateQueries({
        queryKey: ["feedback-comments", itemId],
      });
      queryClient.invalidateQueries({ queryKey: ["feedback-item", itemId] });
      queryClient.invalidateQueries({ queryKey: ["feedback"] }); // Update comment count in list
    },
  });

  // Status update mutation (admin only)
  const statusMutation = useMutation({
    mutationFn: (newStatus: FeedbackStatus) =>
      feedbackApi.updateStatus(itemId, newStatus),
    onSuccess: () => {
      // Refetch to show updated status
      queryClient.invalidateQueries({ queryKey: ["feedback-item", itemId] });
      queryClient.invalidateQueries({ queryKey: ["feedback"] }); // Update list view
    },
  });

  const handleVote = () => {
    voteMutation.mutate();
  };

  const handleCommentSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (commentContent.length < 1) {
      setCommentError("Comment cannot be empty");
      return;
    }
    if (commentContent.length > 5000) {
      setCommentError("Comment must be less than 5,000 characters");
      return;
    }

    commentMutation.mutate(commentContent);
  };

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newStatus = e.target.value as FeedbackStatus;
    statusMutation.mutate(newStatus);
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  if (isLoading) {
    return (
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
        </div>
      </div>
    );
  }

  if (error || !item) {
    return (
      <div
        className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
        onClick={handleBackdropClick}
      >
        <div className="bg-white rounded-2xl shadow-2xl p-8 max-w-md">
          <p className="text-red-700 mb-4">Failed to load feedback item.</p>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const statusConfig = STATUS_COLORS[item.status];

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 overflow-y-auto"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full my-8">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-2xl">
                {item.type === "feature" ? "✨" : "🐛"}
              </span>
              <h2 className="text-2xl font-bold text-gray-900 flex-1">
                {item.title}
              </h2>
            </div>
            <div className="flex items-center gap-4 text-sm text-gray-500">
              {/* Status - Dropdown for admin, badge for others */}
              {isAdmin ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-gray-600">
                    Status:
                  </span>
                  <select
                    value={item.status}
                    onChange={handleStatusChange}
                    disabled={statusMutation.isPending}
                    className={`px-2.5 py-0.5 rounded-md text-xs font-medium border ${statusConfig.bg} ${statusConfig.text} ${statusConfig.border} cursor-pointer hover:brightness-95 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-wait`}
                  >
                    <option value="under_consideration">
                      {STATUS_LABELS.under_consideration}
                    </option>
                    <option value="planned">{STATUS_LABELS.planned}</option>
                    <option value="in_progress">
                      {STATUS_LABELS.in_progress}
                    </option>
                    <option value="completed">{STATUS_LABELS.completed}</option>
                  </select>
                  {statusMutation.isPending && (
                    <span className="text-xs text-blue-600">Updating...</span>
                  )}
                </div>
              ) : (
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium border ${statusConfig.bg} ${statusConfig.text} ${statusConfig.border}`}
                >
                  {STATUS_LABELS[item.status]}
                </span>
              )}
              <span>by {item.authorUsername || "Unknown"}</span>
              <span>{new Date(item.createdAt).toLocaleDateString()}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
          >
            <svg
              className="w-6 h-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="max-h-[calc(100vh-200px)] overflow-y-auto">
          <div className="px-6 py-6">
            {/* Vote Section */}
            <div className="mb-6 flex items-center gap-4">
              <button
                onClick={handleVote}
                disabled={voteMutation.isPending}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold transition-all ${
                  item.hasVoted
                    ? "bg-blue-500 text-white hover:bg-blue-600"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                } ${voteMutation.isPending ? "opacity-50 cursor-wait" : ""}`}
              >
                <svg
                  className="w-5 h-5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                >
                  <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z" />
                </svg>
                <span>
                  {item.hasVoted ? "Voted" : "Vote"} ({item.voteCount})
                </span>
              </button>
            </div>

            {/* Description (Markdown) */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Description
              </h3>
              <div className="prose prose-sm max-w-none text-gray-700">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {item.description}
                </ReactMarkdown>
              </div>
            </div>

            {/* Comments Section */}
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Comments ({comments.length})
              </h3>

              {comments.length === 0 ? (
                <p className="text-gray-500 text-sm italic py-4">
                  No comments yet. Be the first to comment!
                </p>
              ) : (
                <div className="space-y-4">
                  {comments.map((comment) => (
                    <div
                      key={comment.comment_id}
                      className="bg-gray-50 rounded-lg p-4"
                    >
                      <div className="flex items-center gap-2 mb-2 text-sm">
                        <span className="font-semibold text-gray-900">
                          {comment.authorUsername || "Unknown"}
                        </span>
                        <span className="text-gray-500">•</span>
                        <span className="text-gray-500">
                          {new Date(comment.createdAt).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="prose prose-sm max-w-none text-gray-700">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {comment.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Comment Form */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Add Comment
              </h3>
              <form onSubmit={handleCommentSubmit}>
                <textarea
                  value={commentContent}
                  onChange={(e) => setCommentContent(e.target.value)}
                  placeholder="Share your thoughts... (Markdown supported)"
                  rows={4}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                  maxLength={5000}
                />
                {commentError && (
                  <p className="mt-1 text-sm text-red-600">{commentError}</p>
                )}
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    {commentContent.length}/5,000 characters
                  </p>
                  <button
                    type="submit"
                    disabled={commentMutation.isPending}
                    className="px-5 py-2.5 text-sm font-semibold bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                  >
                    {commentMutation.isPending ? "Posting..." : "Post Comment"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
