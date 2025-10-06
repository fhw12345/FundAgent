/**
 * Authentication service for email-based login.
 * Handles verification code sending, verification, and JWT token management.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface User {
  user_id: string;
  email: string | null;
  phone_number: string | null;
  wechat_openid: string | null;
  username: string;
  created_at: string;
  last_login: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface SendCodeResponse {
  message: string;
  code?: string; // Only in dev mode
}

/**
 * Send verification code to email
 */
export async function sendVerificationCode(
  email: string,
): Promise<SendCodeResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/send-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      auth_type: "email",
      identifier: email,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to send verification code");
  }

  return response.json();
}

/**
 * Verify code and login
 */
export async function verifyCodeAndLogin(
  email: string,
  code: string,
): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE_URL}/api/auth/verify-code`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      auth_type: "email",
      identifier: email,
      code: code,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to verify code");
  }

  return response.json();
}

/**
 * Get current user from token
 */
export async function getCurrentUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/api/auth/me?token=${token}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Invalid or expired token");
  }

  return response.json();
}

/**
 * Auth token storage in localStorage
 */
export const authStorage = {
  getToken(): string | null {
    return localStorage.getItem("auth_token");
  },

  setToken(token: string): void {
    localStorage.setItem("auth_token", token);
  },

  removeToken(): void {
    localStorage.removeItem("auth_token");
  },

  getUser(): User | null {
    const userStr = localStorage.getItem("auth_user");
    return userStr ? JSON.parse(userStr) : null;
  },

  setUser(user: User): void {
    localStorage.setItem("auth_user", JSON.stringify(user));
  },

  removeUser(): void {
    localStorage.removeItem("auth_user");
  },

  clear(): void {
    this.removeToken();
    this.removeUser();
  },
};
