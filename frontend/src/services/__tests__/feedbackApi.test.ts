/**
 * Unit tests for feedback API service
 *
 * Tests feedback & community roadmap platform API:
 * - listItems, getItem, createItem (CRUD)
 * - voteItem, unvoteItem (voting)
 * - getComments, addComment (comments)
 * - updateStatus (admin)
 * - generateUploadUrl, uploadImageToOSS (image upload)
 * - exportFeedback (Markdown export)
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { feedbackApi } from "../feedbackApi";
import axios from "axios";

// Mock axios
vi.mock("axios", () => {
  const mockAxios = {
    create: vi.fn(() => mockAxios),
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    put: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return { default: mockAxios };
});

// Mock auth storage
vi.mock("../authService", () => ({
  authStorage: {
    getToken: vi.fn(() => "mock-token"),
  },
}));

describe("feedbackApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ===== listItems Tests =====

  describe("listItems", () => {
    it("should list all items without filter", async () => {
      // Arrange
      const mockResponse = {
        data: [
          {
            item_id: "f1",
            type: "feature_request",
            title: "Add dark mode",
            votes: 42,
          },
          {
            item_id: "f2",
            type: "bug_report",
            title: "Fix login issue",
            votes: 15,
          },
        ],
      };
      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.listItems();

      // Assert
      expect(axios.get).toHaveBeenCalledWith("/api/feedback/items", {
        params: {},
      });
      expect(result).toHaveLength(2);
    });

    it("should filter items by type", async () => {
      // Arrange
      const mockResponse = {
        data: [
          {
            item_id: "f1",
            type: "feature_request",
            title: "Feature 1",
            votes: 10,
          },
        ],
      };
      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.listItems("feature_request");

      // Assert
      expect(axios.get).toHaveBeenCalledWith("/api/feedback/items", {
        params: { type: "feature_request" },
      });
      expect(result[0].type).toBe("feature_request");
    });
  });

  // ===== getItem Tests =====

  describe("getItem", () => {
    it("should get single feedback item", async () => {
      // Arrange
      const mockResponse = {
        data: {
          item_id: "f1",
          type: "feature_request",
          title: "Add export feature",
          description: "Allow exporting data to CSV",
          votes: 25,
          status: "planned",
        },
      };
      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.getItem("f1");

      // Assert
      expect(axios.get).toHaveBeenCalledWith("/api/feedback/items/f1");
      expect(result.item_id).toBe("f1");
      expect(result.status).toBe("planned");
    });
  });

  // ===== createItem Tests =====

  describe("createItem", () => {
    it("should create new feedback item", async () => {
      // Arrange
      const newItem = {
        type: "feature_request" as const,
        title: "New feature",
        description: "Feature description",
      };
      const mockResponse = {
        data: {
          item_id: "f3",
          ...newItem,
          votes: 0,
          status: "under_consideration",
          created_at: "2025-01-31T12:00:00Z",
        },
      };
      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.createItem(newItem);

      // Assert
      expect(axios.post).toHaveBeenCalledWith("/api/feedback/items", newItem);
      expect(result.item_id).toBe("f3");
      expect(result.votes).toBe(0);
    });
  });

  // ===== voteItem Tests =====

  describe("voteItem", () => {
    it("should vote for item", async () => {
      // Arrange
      vi.mocked(axios.post).mockResolvedValueOnce({});

      // Act
      await feedbackApi.voteItem("f1");

      // Assert
      expect(axios.post).toHaveBeenCalledWith("/api/feedback/items/f1/vote");
    });
  });

  // ===== unvoteItem Tests =====

  describe("unvoteItem", () => {
    it("should remove vote from item", async () => {
      // Arrange
      vi.mocked(axios.delete).mockResolvedValueOnce({});

      // Act
      await feedbackApi.unvoteItem("f1");

      // Assert
      expect(axios.delete).toHaveBeenCalledWith("/api/feedback/items/f1/vote");
    });
  });

  // ===== getComments Tests =====

  describe("getComments", () => {
    it("should get comments for item", async () => {
      // Arrange
      const mockResponse = {
        data: [
          {
            comment_id: "c1",
            content: "Great idea!",
            created_at: "2025-01-31T12:00:00Z",
          },
          {
            comment_id: "c2",
            content: "I agree",
            created_at: "2025-01-31T13:00:00Z",
          },
        ],
      };
      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.getComments("f1");

      // Assert
      expect(axios.get).toHaveBeenCalledWith("/api/feedback/items/f1/comments");
      expect(result).toHaveLength(2);
    });
  });

  // ===== addComment Tests =====

  describe("addComment", () => {
    it("should add comment to item", async () => {
      // Arrange
      const mockResponse = {
        data: {
          comment_id: "c3",
          content: "Nice feature!",
          created_at: "2025-01-31T14:00:00Z",
        },
      };
      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.addComment("f1", "Nice feature!");

      // Assert
      expect(axios.post).toHaveBeenCalledWith("/api/feedback/items/f1/comments", {
        content: "Nice feature!",
      });
      expect(result.content).toBe("Nice feature!");
    });
  });

  // ===== exportFeedback Tests =====

  describe("exportFeedback", () => {
    it("should export feedback as markdown", async () => {
      // Arrange
      const mockResponse = {
        data: "# Feedback Export\n\n## Feature Requests\n- Item 1\n- Item 2",
      };
      vi.mocked(axios.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.exportFeedback();

      // Assert
      expect(axios.get).toHaveBeenCalledWith("/api/feedback/export");
      expect(result).toContain("# Feedback Export");
      expect(result).toContain("Feature Requests");
    });
  });

  // ===== updateStatus Tests =====

  describe("updateStatus", () => {
    it("should update item status to planned", async () => {
      // Arrange
      const mockResponse = {
        data: {
          item_id: "f1",
          status: "planned",
          title: "Feature",
        },
      };
      vi.mocked(axios.patch).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.updateStatus("f1", "planned");

      // Assert
      expect(axios.patch).toHaveBeenCalledWith("/api/feedback/items/f1/status", {
        status: "planned",
      });
      expect(result.status).toBe("planned");
    });

    it("should support all status values", async () => {
      // Arrange
      const mockResponse = { data: { item_id: "f1", status: "completed" } };
      vi.mocked(axios.patch).mockResolvedValue(mockResponse);

      // Act & Assert - under_consideration
      await feedbackApi.updateStatus("f1", "under_consideration");
      expect(axios.patch).toHaveBeenCalledWith("/api/feedback/items/f1/status", {
        status: "under_consideration",
      });

      // Act & Assert - in_progress
      await feedbackApi.updateStatus("f1", "in_progress");
      expect(axios.patch).toHaveBeenCalledWith("/api/feedback/items/f1/status", {
        status: "in_progress",
      });

      // Act & Assert - completed
      await feedbackApi.updateStatus("f1", "completed");
      expect(axios.patch).toHaveBeenCalledWith("/api/feedback/items/f1/status", {
        status: "completed",
      });
    });
  });

  // ===== generateUploadUrl Tests =====

  describe("generateUploadUrl", () => {
    it("should generate presigned URL for image upload", async () => {
      // Arrange
      const mockResponse = {
        data: {
          upload_url: "https://oss.example.com/presigned-url",
          public_url: "https://oss.example.com/feedback/image.png",
        },
      };
      vi.mocked(axios.post).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await feedbackApi.generateUploadUrl({
        filename: "screenshot.png",
        content_type: "image/png",
      });

      // Assert
      expect(axios.post).toHaveBeenCalledWith("/api/feedback/upload-image", {
        filename: "screenshot.png",
        content_type: "image/png",
      });
      expect(result.upload_url).toContain("presigned-url");
      expect(result.public_url).toContain("image.png");
    });
  });

  // ===== uploadImageToOSS Tests =====

  describe("uploadImageToOSS", () => {
    it("should upload image to OSS using presigned URL", async () => {
      // Arrange
      const mockFile = new File(["image content"], "test.png", {
        type: "image/png",
      });
      vi.mocked(axios.put).mockResolvedValueOnce({});

      // Act
      await feedbackApi.uploadImageToOSS(
        "https://oss.example.com/presigned-url",
        mockFile,
      );

      // Assert
      expect(axios.put).toHaveBeenCalledWith(
        "https://oss.example.com/presigned-url",
        mockFile,
        {
          headers: {
            "Content-Type": "image/png",
          },
        },
      );
    });

    it("should handle different image types", async () => {
      // Arrange
      const mockFile = new File(["image content"], "photo.jpg", {
        type: "image/jpeg",
      });
      vi.mocked(axios.put).mockResolvedValueOnce({});

      // Act
      await feedbackApi.uploadImageToOSS("https://oss.example.com/url", mockFile);

      // Assert
      expect(axios.put).toHaveBeenCalledWith(
        "https://oss.example.com/url",
        mockFile,
        {
          headers: {
            "Content-Type": "image/jpeg",
          },
        },
      );
    });
  });

  // ===== Integration Tests =====

  describe("Integration - Complete feedback workflow", () => {
    it("should perform full feedback submission with image", async () => {
      // Arrange
      const mockListResponse = { data: [] };
      const mockCreateResponse = {
        data: {
          item_id: "f1",
          type: "feature_request",
          title: "New feature",
          votes: 0,
        },
      };
      const mockUploadUrlResponse = {
        data: {
          upload_url: "https://oss.example.com/upload",
          public_url: "https://oss.example.com/image.png",
        },
      };
      const mockFile = new File(["content"], "screenshot.png", {
        type: "image/png",
      });

      vi.mocked(axios.get).mockResolvedValueOnce(mockListResponse);
      vi.mocked(axios.post)
        .mockResolvedValueOnce(mockCreateResponse)
        .mockResolvedValueOnce(mockUploadUrlResponse)
        .mockResolvedValueOnce({});
      vi.mocked(axios.put).mockResolvedValueOnce({});

      // Act - List existing items
      const items = await feedbackApi.listItems();
      expect(items).toHaveLength(0);

      // Act - Create new item
      const newItem = await feedbackApi.createItem({
        type: "feature_request",
        title: "New feature",
        description: "Description",
      });
      expect(newItem.item_id).toBe("f1");

      // Act - Generate upload URL
      const uploadInfo = await feedbackApi.generateUploadUrl({
        filename: "screenshot.png",
        content_type: "image/png",
      });
      expect(uploadInfo.upload_url).toBeDefined();

      // Act - Upload image to OSS
      await feedbackApi.uploadImageToOSS(uploadInfo.upload_url, mockFile);

      // Act - Vote for item
      await feedbackApi.voteItem("f1");
      expect(axios.post).toHaveBeenCalledWith("/api/feedback/items/f1/vote");
    });
  });
});
