/**
 * Image Upload Widget for Feedback Attachments
 *
 * Features:
 * - Drag & drop support
 * - File validation (type, size)
 * - Upload progress tracking
 * - Image preview thumbnails
 * - Max 5 images
 */

import { useState, useRef } from "react";
import { Upload, X, Loader2 } from "lucide-react";
import { feedbackApi } from "../../services/feedbackApi";

interface ImageUploadWidgetProps {
  onImagesUploaded: (imageUrls: string[]) => void;
  maxImages?: number;
}

interface UploadingImage {
  file: File;
  preview: string;
  progress: number;
  error?: string;
}

const ALLOWED_TYPES = ["image/png", "image/jpeg", "image/gif", "image/webp"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function ImageUploadWidget({
  onImagesUploaded,
  maxImages = 5,
}: ImageUploadWidgetProps) {
  const [uploadedImages, setUploadedImages] = useState<string[]>([]);
  const [uploadingImages, setUploadingImages] = useState<UploadingImage[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return `Invalid file type. Allowed: PNG, JPEG, GIF, WebP`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large. Max size: 10MB`;
    }
    return null;
  };

  const uploadImage = async (file: File) => {
    const preview = URL.createObjectURL(file);
    const uploadingImage: UploadingImage = {
      file,
      preview,
      progress: 0,
    };

    setUploadingImages((prev) => [...prev, uploadingImage]);

    try {
      // Step 1: Get presigned URL
      const uploadData = await feedbackApi.generateUploadUrl({
        filename: file.name,
        content_type: file.type,
      });

      // Update progress
      setUploadingImages((prev) =>
        prev.map((img) =>
          img.preview === preview ? { ...img, progress: 50 } : img,
        ),
      );

      // Step 2: Upload to OSS
      await feedbackApi.uploadImageToOSS(uploadData.upload_url, file);

      // Update progress
      setUploadingImages((prev) =>
        prev.map((img) =>
          img.preview === preview ? { ...img, progress: 100 } : img,
        ),
      );

      // Add to uploaded images
      const newUploadedImages = [...uploadedImages, uploadData.public_url];
      setUploadedImages(newUploadedImages);
      onImagesUploaded(newUploadedImages);

      // Remove from uploading list after brief delay
      setTimeout(() => {
        setUploadingImages((prev) =>
          prev.filter((img) => img.preview !== preview),
        );
        URL.revokeObjectURL(preview);
      }, 500);
    } catch (error) {
      // Mark as error
      setUploadingImages((prev) =>
        prev.map((img) =>
          img.preview === preview
            ? {
                ...img,
                error:
                  error instanceof Error ? error.message : "Upload failed",
              }
            : img,
        ),
      );
    }
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;

    const totalImages =
      uploadedImages.length + uploadingImages.length + files.length;
    if (totalImages > maxImages) {
      alert(`Maximum ${maxImages} images allowed`);
      return;
    }

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const error = validateFile(file);

      if (error) {
        alert(`${file.name}: ${error}`);
        continue;
      }

      await uploadImage(file);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const removeUploadedImage = (url: string) => {
    const newUploadedImages = uploadedImages.filter((img) => img !== url);
    setUploadedImages(newUploadedImages);
    onImagesUploaded(newUploadedImages);
  };

  const retryUpload = (uploadingImage: UploadingImage) => {
    // Remove from uploading list
    setUploadingImages((prev) =>
      prev.filter((img) => img.preview !== uploadingImage.preview),
    );
    // Retry upload
    uploadImage(uploadingImage.file);
  };

  const canUploadMore =
    uploadedImages.length + uploadingImages.length < maxImages;

  return (
    <div className="space-y-3">
      {/* Upload Area */}
      {canUploadMore && (
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`
            border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-all
            ${
              isDragging
                ? "border-blue-500 bg-blue-50"
                : "border-gray-300 hover:border-gray-400 hover:bg-gray-50"
            }
          `}
        >
          <Upload
            className={`w-8 h-8 mx-auto mb-2 ${isDragging ? "text-blue-500" : "text-gray-400"}`}
          />
          <p className="text-sm text-gray-600 font-medium">
            {isDragging
              ? "Drop images here"
              : "Click to upload or drag and drop"}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            PNG, JPG, GIF, WebP (max 10MB, up to {maxImages} images)
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept={ALLOWED_TYPES.join(",")}
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      )}

      {/* Uploaded Images */}
      {uploadedImages.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {uploadedImages.map((url, index) => (
            <div
              key={url}
              className="relative group aspect-square rounded-lg overflow-hidden border border-gray-200 bg-gray-100"
            >
              <img
                src={url}
                alt={`Uploaded ${index + 1}`}
                className="w-full h-full object-cover"
              />
              <button
                onClick={() => removeUploadedImage(url)}
                className="absolute top-1 right-1 p-1 bg-red-500 text-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600"
                title="Remove image"
              >
                <X size={14} />
              </button>
              <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/50 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                <p className="text-xs text-white truncate">
                  Image {index + 1}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Uploading Progress */}
      {uploadingImages.length > 0 && (
        <div className="space-y-2">
          {uploadingImages.map((uploadingImage) => (
            <div
              key={uploadingImage.preview}
              className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg border border-gray-200"
            >
              <div className="w-12 h-12 rounded overflow-hidden border border-gray-300 flex-shrink-0">
                <img
                  src={uploadingImage.preview}
                  alt="Uploading"
                  className="w-full h-full object-cover"
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {uploadingImage.file.name}
                </p>
                {uploadingImage.error ? (
                  <div className="flex items-center gap-2">
                    <p className="text-xs text-red-600">
                      {uploadingImage.error}
                    </p>
                    <button
                      onClick={() => retryUpload(uploadingImage)}
                      className="text-xs text-blue-600 hover:underline"
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-gray-200 rounded-full h-1.5">
                      <div
                        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
                        style={{ width: `${uploadingImage.progress}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-500">
                      {uploadingImage.progress}%
                    </span>
                  </div>
                )}
              </div>
              {!uploadingImage.error && uploadingImage.progress < 100 && (
                <Loader2 className="w-4 h-4 text-blue-500 animate-spin flex-shrink-0" />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Image Count */}
      {uploadedImages.length > 0 && (
        <p className="text-xs text-gray-500 text-center">
          {uploadedImages.length} / {maxImages} images uploaded
        </p>
      )}
    </div>
  );
}
