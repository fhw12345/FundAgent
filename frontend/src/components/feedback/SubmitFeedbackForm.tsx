/**
 * Submit Feedback Form Modal
 * Allows users to create new feature requests or bug reports.
 */

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import type { FeedbackType } from "../../types/feedback";
import { feedbackApi } from "../../services/feedbackApi";
import { ImageUploadWidget } from "./ImageUploadWidget";

interface SubmitFeedbackFormProps {
  onClose: () => void;
}

export function SubmitFeedbackForm({ onClose }: SubmitFeedbackFormProps) {
  const { t } = useTranslation(["feedback", "common", "validation"]);
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
      newErrors.title = t("validation:feedback.titleMinLength", { min: 5 });
    }
    if (title.length > 200) {
      newErrors.title = t("validation:feedback.titleMaxLength", { max: 200 });
    }
    if (description.length < 10) {
      newErrors.description = t("validation:feedback.descriptionMinLength", {
        min: 10,
      });
    }
    if (description.length > 10000) {
      newErrors.description = t("validation:feedback.descriptionMaxLength", {
        max: "10,000",
      });
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
          <h2 className="text-2xl font-bold text-gray-900">
            {t("feedback:form.header")}
          </h2>
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
              {t("feedback:form.type")}
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
                        {t("feedback:form.types.feature")}
                      </div>
                      <div className="text-sm text-gray-600">
                        {t("feedback:form.types.featureDescription")}
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
                        {t("feedback:form.types.bug")}
                      </div>
                      <div className="text-sm text-gray-600">
                        {t("feedback:form.types.bugDescription")}
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
              {t("feedback:form.titleRequired")}
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("feedback:form.titlePlaceholder")}
              className={`w-full px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                errors.title ? "border-red-500" : "border-gray-300"
              }`}
              maxLength={200}
            />
            {errors.title && (
              <p className="mt-1 text-sm text-red-600">{errors.title}</p>
            )}
            <p className="mt-1 text-sm text-gray-500">
              {t("feedback:form.charactersCount", {
                current: title.length,
                max: 200,
              })}
            </p>
          </div>

          {/* Description */}
          <div className="mb-6">
            <label
              htmlFor="description"
              className="block text-sm font-semibold text-gray-700 mb-2"
            >
              {t("feedback:form.descriptionRequired")}
            </label>
            <textarea
              id="description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("feedback:form.descriptionPlaceholder")}
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
              {t("feedback:form.charactersCount", {
                current: description.length,
                max: "10,000",
              })}{" "}
              · {t("feedback:form.markdownSupported")}
            </p>
          </div>

          {/* Image Attachments */}
          <div className="mb-6">
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              {t("feedback:form.attachments")}
            </label>
            <ImageUploadWidget onImagesUploaded={setImageUrls} />
          </div>

          {/* Error Message */}
          {createMutation.isError && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-red-700">{t("feedback:form.failed")}</p>
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
            {t("common:buttons.cancel")}
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={createMutation.isPending}
            className="px-5 py-2.5 text-sm font-semibold bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
          >
            {createMutation.isPending
              ? t("feedback:form.submitting")
              : t("feedback:form.submit")}
          </button>
        </div>
      </div>
    </div>
  );
}
