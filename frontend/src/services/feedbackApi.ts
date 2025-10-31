/**
 * API client for Feedback & Community Roadmap platform.
 */

import axios from "axios";
import type {
  Comment,
  CommentCreate,
  FeedbackImageUploadRequest,
  FeedbackImageUploadResponse,
  FeedbackItem,
  FeedbackItemCreate,
  FeedbackType,
} from "../types/feedback";
import { authStorage } from "./authService";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";

// Create axios instance with auth header injection
const api = axios.create({
  baseURL: API_BASE_URL,
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = authStorage.getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const feedbackApi = {
  /**
   * List feedback items, optionally filtered by type.
   */
  async listItems(type?: FeedbackType): Promise<FeedbackItem[]> {
    const params = type ? { type } : {};
    const response = await api.get<FeedbackItem[]>("/api/feedback/items", {
      params,
    });
    return response.data;
  },

  /**
   * Get a single feedback item by ID.
   */
  async getItem(itemId: string): Promise<FeedbackItem> {
    const response = await api.get<FeedbackItem>(
      `/api/feedback/items/${itemId}`,
    );
    return response.data;
  },

  /**
   * Create a new feedback item.
   */
  async createItem(data: FeedbackItemCreate): Promise<FeedbackItem> {
    const response = await api.post<FeedbackItem>("/api/feedback/items", data);
    return response.data;
  },

  /**
   * Cast a vote for a feedback item.
   */
  async voteItem(itemId: string): Promise<void> {
    await api.post(`/api/feedback/items/${itemId}/vote`);
  },

  /**
   * Remove a vote from a feedback item.
   */
  async unvoteItem(itemId: string): Promise<void> {
    await api.delete(`/api/feedback/items/${itemId}/vote`);
  },

  /**
   * Get all comments for a feedback item.
   */
  async getComments(itemId: string): Promise<Comment[]> {
    const response = await api.get<Comment[]>(
      `/api/feedback/items/${itemId}/comments`,
    );
    return response.data;
  },

  /**
   * Add a comment to a feedback item.
   */
  async addComment(itemId: string, content: string): Promise<Comment> {
    const data: CommentCreate = { content };
    const response = await api.post<Comment>(
      `/api/feedback/items/${itemId}/comments`,
      data,
    );
    return response.data;
  },

  /**
   * Export all feedback as Markdown.
   */
  async exportFeedback(): Promise<string> {
    const response = await api.get<string>("/api/feedback/export");
    return response.data;
  },

  /**
   * Update feedback item status (admin only).
   */
  async updateStatus(
    itemId: string,
    status: "under_consideration" | "planned" | "in_progress" | "completed",
  ): Promise<FeedbackItem> {
    const response = await api.patch<FeedbackItem>(
      `/api/feedback/items/${itemId}/status`,
      { status },
    );
    return response.data;
  },

  /**
   * Generate presigned URL for uploading an image.
   */
  async generateUploadUrl(
    request: FeedbackImageUploadRequest,
  ): Promise<FeedbackImageUploadResponse> {
    const response = await api.post<FeedbackImageUploadResponse>(
      "/api/feedback/upload-image",
      request,
    );
    return response.data;
  },

  /**
   * Upload image file to OSS using presigned URL.
   */
  async uploadImageToOSS(
    presignedUrl: string,
    file: File,
  ): Promise<void> {
    await axios.put(presignedUrl, file, {
      headers: {
        "Content-Type": file.type,
      },
    });
  },
};
