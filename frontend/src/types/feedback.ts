/**
 * Type definitions for Feedback & Community Roadmap platform.
 */

export type FeedbackType = "feature" | "bug";

export type FeedbackStatus =
  | "under_consideration"
  | "planned"
  | "in_progress"
  | "completed";

export interface FeedbackItem {
  item_id: string;
  title: string;
  description: string;
  authorId: string;
  type: FeedbackType;
  status: FeedbackStatus;
  voteCount: number;
  commentCount: number;
  createdAt: string;
  updatedAt: string;
  hasVoted: boolean;
  authorUsername?: string;
}

export interface FeedbackItemCreate {
  title: string;
  description: string;
  type: FeedbackType;
}

export interface Comment {
  comment_id: string;
  itemId: string;
  authorId: string;
  content: string;
  createdAt: string;
  authorUsername?: string;
}

export interface CommentCreate {
  content: string;
}

// UI-friendly status display
export const STATUS_LABELS: Record<FeedbackStatus, string> = {
  under_consideration: "Under Consideration",
  planned: "Planned",
  in_progress: "In Progress",
  completed: "Completed",
};

// Status badge colors
export const STATUS_COLORS: Record<
  FeedbackStatus,
  { bg: string; text: string; border: string }
> = {
  under_consideration: {
    bg: "bg-gray-100",
    text: "text-gray-700",
    border: "border-gray-300",
  },
  planned: {
    bg: "bg-blue-100",
    text: "text-blue-700",
    border: "border-blue-300",
  },
  in_progress: {
    bg: "bg-yellow-100",
    text: "text-yellow-700",
    border: "border-yellow-300",
  },
  completed: {
    bg: "bg-green-100",
    text: "text-green-700",
    border: "border-green-300",
  },
};
