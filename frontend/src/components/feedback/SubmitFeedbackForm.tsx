/**
 * Submit Feedback Form Modal
 * Allows users to create new feature requests or bug reports.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { FeedbackType } from "../../types/feedback";
import { feedbackApi } from "../../services/feedbackApi";
import { ImageUploadWidget } from "./ImageUploadWidget";

interface SubmitFeedbackFormProps {
  onClose: () => void;
}

export function SubmitFeedbackForm({ onClose }: SubmitFeedbackFormProps) {
  const [type, setType] = useState<FeedbackType>("feature");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [imageUrls, setImageUrls] = useState<string[]>([]);
  const [errors, setErrors] = useState<{
    title?: string;
    description?: string;
  }>({});

  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: feedbackApi.createItem,
    onSuccess: () => {
      // Invalidate both leaderboards to refetch
      void queryClient.invalidateQueries({ queryKey: ["feedback"] });
      onClose();
    },
  });

  const validate = () => {
    const newErrors: { title?: string; description?: string } = {};

    if (title.length < 5) {
      newErrors.title = "Title must be at least 5 characters";
    }
    if (title.length > 200) {
      newErrors.title = "Title must be less than 200 characters";
    }
    if (description.length < 10) {
      newErrors.description = "Description must be at least 10 characters";
    }
    if (description.length > 10000) {
      newErrors.description = "Description must be less than 10,000 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) {
      return;
    }

    createMutation.mutate({
      title,
      description,
      type,
      image_urls: imageUrls,
    });
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-900">Submit Feedback</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
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

        {/* Form */}
        <form
          onSubmit={handleSubmit}
          className="p-6 overflow-y-auto max-h-[calc(90vh-200px)]"
        >
          {/* Type Selection */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Type
            </label>
            <div className="flex gap-4">
              <label className="flex-1">
                <input
                  type="radio"
                  name="type"
                  value="feature"
                  checked={type === "feature"}
                  onChange={(e) => setType(e.target.value as FeedbackType)}
                  className="sr-only peer"
                />
                <div className="p-4 border-2 border-gray-200 rounded-xl cursor-pointer transition-all peer-checked:border-blue-500 peer-checked:bg-blue-50 hover:border-gray-300">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">✨</span>
                    <div>
                      <div className="font-semibold text-gray-900">
                        Feature Request
                      </div>
                      <div className="text-sm text-gray-600">
                        Suggest a new feature
                      </div>
                    </div>
                  </div>
                </div>
              </label>
              <label className="flex-1">
                <input
                  type="radio"
                  name="type"
                  value="bug"
                  checked={type === "bug"}
                  onChange={(e) => setType(e.target.value as FeedbackType)}
                  className="sr-only peer"
                />
                <div className="p-4 border-2 border-gray-200 rounded-xl cursor-pointer transition-all peer-checked:border-blue-500 peer-checked:bg-blue-50 hover:border-gray-300">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">🐛</span>
                    <div>
                      <div className="font-semibold text-gray-900">
                        Bug Report
                      </div>
                      <div className="text-sm text-gray-600">
                        Report an issue
                      </div>
                    </div>
                  </div>
                </div>
              </label>
            </div>
          </div>

          {/* Title */}
          <div className="mb-6">
            <label
              htmlFor="title"
              className="block text-sm font-semibold text-gray-700 mb-2"
            >
              Title *
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Brief summary of your feedback"
              className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.title ? "border-red-500" : "border-gray-300"
              }`}
              maxLength={200}
            />
            {errors.title && (
              <p className="mt-1 text-sm text-red-600">{errors.title}</p>
            )}
            <p className="mt-1 text-sm text-gray-500">
              {title.length}/200 characters
            </p>
          </div>

          {/* Description */}
          <div className="mb-6">
            <label
              htmlFor="description"
              className="block text-sm font-semibold text-gray-700 mb-2"
            >
              Description *
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Provide detailed information. Markdown is supported."
              rows={8}
              className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-sm ${
                errors.description ? "border-red-500" : "border-gray-300"
              }`}
              maxLength={10000}
            />
            {errors.description && (
              <p className="mt-1 text-sm text-red-600">{errors.description}</p>
            )}
            <p className="mt-1 text-sm text-gray-500">
              {description.length}/10,000 characters · Markdown supported
            </p>
          </div>

          {/* Image Attachments */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Attachments (Optional)
            </label>
            <ImageUploadWidget onImagesUploaded={setImageUrls} />
          </div>

          {/* Error Message */}
          {createMutation.isError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700">
                Failed to submit feedback. Please try again.
              </p>
            </div>
          )}
        </form>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-5 py-2.5 text-sm font-semibold text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={createMutation.isPending}
            className="px-5 py-2.5 text-sm font-semibold bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {createMutation.isPending ? "Submitting..." : "Submit Feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}
