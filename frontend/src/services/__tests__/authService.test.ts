/**
 * Unit tests for authService.
 *
 * Tests authentication service including:
 * - Send verification code
 * - Verify code and login
 * - User registration
 * - Login with password
 * - Password reset
 * - Token refresh
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  sendVerificationCode,
  verifyCodeAndLogin,
  registerUser,
  loginWithPassword,
  resetPassword,
  refreshAccessToken,
  logout,
  type LoginResponse,
  type SendCodeResponse,
} from "../authService";

// Mock fetch globally
global.fetch = vi.fn();

describe("authService", () => {
  beforeEach(() => {
    // Reset mock before each test
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("sendVerificationCode", () => {
    it("should send verification code successfully", async () => {
      // Arrange
      const mockResponse: SendCodeResponse = {
        message: "Verification code sent",
        code: "123456",
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await sendVerificationCode("test@example.com");

      // Assert
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/send-code"),
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            auth_type: "email",
            identifier: "test@example.com",
          }),
        })
      );
    });

    it("should throw error on failed request", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid email" }),
      });

      // Act & Assert
      await expect(
        sendVerificationCode("invalid@example.com")
      ).rejects.toThrow("Invalid email");
    });
  });

  describe("verifyCodeAndLogin", () => {
    it("should verify code and login successfully", async () => {
      // Arrange
      const mockResponse: LoginResponse = {
        access_token: "access_token_123",
        refresh_token: "refresh_token_456",
        token_type: "Bearer",
        expires_in: 604800,
        refresh_expires_in: 2592000,
        user: {
          user_id: "user_123",
          email: "test@example.com",
          phone_number: null,
          wechat_openid: null,
          username: "testuser",
          is_admin: false,
          created_at: "2024-01-01T00:00:00",
          last_login: "2024-01-10T00:00:00",
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await verifyCodeAndLogin("test@example.com", "123456");

      // Assert
      expect(result).toEqual(mockResponse);
      expect(result.user.email).toBe("test@example.com");
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/verify-code"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should throw error on invalid code", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid verification code" }),
      });

      // Act & Assert
      await expect(
        verifyCodeAndLogin("test@example.com", "wrong")
      ).rejects.toThrow("Invalid verification code");
    });
  });

  describe("registerUser", () => {
    it("should register new user successfully", async () => {
      // Arrange
      const mockResponse: LoginResponse = {
        access_token: "new_access_token",
        refresh_token: "new_refresh_token",
        token_type: "Bearer",
        expires_in: 604800,
        refresh_expires_in: 2592000,
        user: {
          user_id: "user_new",
          email: "newuser@example.com",
          phone_number: null,
          wechat_openid: null,
          username: "newuser",
          is_admin: false,
          created_at: "2024-01-10T00:00:00",
          last_login: null,
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await registerUser(
        "newuser@example.com",
        "123456",
        "newuser",
        "SecureP@ssw0rd"
      );

      // Assert
      expect(result).toEqual(mockResponse);
      expect(result.user.username).toBe("newuser");
    });

    it("should throw error on duplicate email", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Email already registered" }),
      });

      // Act & Assert
      await expect(
        registerUser("duplicate@example.com", "123456", "user", "password")
      ).rejects.toThrow("Email already registered");
    });
  });

  describe("loginWithPassword", () => {
    it("should login with password successfully", async () => {
      // Arrange
      const mockResponse: LoginResponse = {
        access_token: "password_access_token",
        refresh_token: "password_refresh_token",
        token_type: "Bearer",
        expires_in: 604800,
        refresh_expires_in: 2592000,
        user: {
          user_id: "user_456",
          email: "existing@example.com",
          phone_number: null,
          wechat_openid: null,
          username: "existinguser",
          is_admin: false,
          created_at: "2023-12-01T00:00:00",
          last_login: "2024-01-10T00:00:00",
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await loginWithPassword(
        "existing@example.com",
        "correctpassword"
      );

      // Assert
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/login"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should throw error on wrong password", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid password" }),
      });

      // Act & Assert
      await expect(
        loginWithPassword("test@example.com", "wrongpassword")
      ).rejects.toThrow("Invalid password");
    });
  });

  describe("resetPassword", () => {
    it("should reset password successfully", async () => {
      // Arrange
      const mockResponse: LoginResponse = {
        access_token: "new_access_token",
        refresh_token: "new_refresh_token",
        token_type: "Bearer",
        expires_in: 604800,
        refresh_expires_in: 2592000,
        user: {
          user_id: "user_123",
          email: "test@example.com",
          phone_number: null,
          wechat_openid: null,
          username: "testuser",
          is_admin: false,
          created_at: "2024-01-01T00:00:00",
          last_login: "2024-01-10T00:00:00",
        },
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await resetPassword(
        "test@example.com",
        "123456",
        "NewP@ssw0rd123"
      );

      // Assert
      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/reset-password"),
        expect.objectContaining({
          method: "POST",
        })
      );
    });

    it("should throw error on invalid code", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid verification code" }),
      });

      // Act & Assert
      await expect(
        resetPassword("test@example.com", "wrong_code", "NewPassword123")
      ).rejects.toThrow("Invalid verification code");
    });
  });

  describe("refreshAccessToken", () => {
    it("should refresh access token successfully", async () => {
      // Arrange
      const mockResponse = {
        access_token: "new_access_token_789",
        token_type: "Bearer",
        expires_in: 604800,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      // Act
      const result = await refreshAccessToken("refresh_token_456");

      // Assert
      expect(result.access_token).toBe("new_access_token_789");
    });

    it("should throw error on expired refresh token", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Refresh token expired" }),
      });

      // Act & Assert
      await expect(
        refreshAccessToken("expired_token")
      ).rejects.toThrow("Refresh token expired");
    });
  });

  describe("logout", () => {
    it("should logout successfully", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ message: "Logged out successfully" }),
      });

      // Act
      await logout("refresh_token_456");

      // Assert
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/logout"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ refresh_token: "refresh_token_456" }),
        })
      );
    });

    it("should throw error on logout failure", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: "Invalid refresh token" }),
      });

      // Act & Assert
      await expect(logout("invalid_token")).rejects.toThrow(
        "Invalid refresh token"
      );
    });
  });

  describe("Error handling", () => {
    it("should handle network errors", async () => {
      // Arrange
      (global.fetch as any).mockRejectedValueOnce(
        new Error("Network error")
      );

      // Act & Assert
      await expect(sendVerificationCode("test@example.com")).rejects.toThrow(
        "Network error"
      );
    });

    it("should handle malformed JSON response", async () => {
      // Arrange
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        json: async () => {
          throw new Error("Invalid JSON");
        },
      });

      // Act & Assert
      await expect(sendVerificationCode("test@example.com")).rejects.toThrow();
    });
  });
});
