/**
 * Token refresh interceptor logic for axios
 * Handles automatic access token refresh before expiry
 *
 * Uses shared authStorage and refreshAccessToken from authService
 * to avoid duplicate localStorage manipulation.
 */

import type { InternalAxiosRequestConfig } from "axios";
import { authStorage, refreshAccessToken } from "./authService";

// Token refresh state (mutex pattern for concurrent requests)
let isRefreshing = false;
let refreshSubscribers: Array<(token: string) => void> = [];

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

function onTokenRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

/**
 * Core token refresh logic - shared by all refresh paths
 * Returns new access token or null if refresh failed
 */
export async function performTokenRefresh(): Promise<string | null> {
  const refreshToken = authStorage.getRefreshToken();
  if (!refreshToken) {
    console.log("[TokenRefresh] No refresh token available");
    return null;
  }

  try {
    console.log("[TokenRefresh] Attempting to refresh access token...");
    const response = await refreshAccessToken(refreshToken);
    authStorage.saveLoginResponse(response);
    console.log("[TokenRefresh] Token refreshed successfully");
    return response.access_token;
  } catch (error) {
    console.error("[TokenRefresh] Refresh failed:", error);
    // Refresh token is invalid - clear auth
    authStorage.clear();
    return null;
  }
}

/**
 * Refresh access token if expiring soon (< 5 minutes)
 * Returns updated config with new token
 *
 * Used by axios request interceptor for proactive refresh.
 */
export async function refreshTokenIfNeeded(
  config: InternalAxiosRequestConfig,
): Promise<InternalAxiosRequestConfig> {
  const accessToken = authStorage.getAccessToken();
  const refreshToken = authStorage.getRefreshToken();

  if (accessToken && refreshToken) {
    // Check if token is expiring soon
    if (authStorage.isAccessTokenExpiringSoon()) {
      if (!isRefreshing) {
        isRefreshing = true;

        try {
          const newToken = await performTokenRefresh();

          isRefreshing = false;

          if (newToken) {
            onTokenRefreshed(newToken);
            if (config.headers) {
              config.headers.Authorization = `Bearer ${newToken}`;
            }
          } else {
            // Refresh failed, redirect to login
            window.location.href = "/login";
          }
        } catch (error) {
          isRefreshing = false;
          console.error("Token refresh failed:", error);
        }
      } else {
        // Wait for ongoing refresh to complete
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken: string) => {
            if (config.headers) {
              config.headers.Authorization = `Bearer ${newToken}`;
            }
            resolve(config);
          });
        });
      }
    } else {
      // Token still valid, use it
      if (config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }
    }
  }

  return config;
}

/**
 * Retry failed 401 request after refreshing token
 *
 * Used by axios response interceptor for reactive refresh.
 * Returns new access token or null if refresh failed.
 */
export async function retryWithRefreshToken(): Promise<string | null> {
  const refreshToken = authStorage.getRefreshToken();

  if (refreshToken && !isRefreshing) {
    isRefreshing = true;

    try {
      const newToken = await performTokenRefresh();

      isRefreshing = false;

      if (newToken) {
        onTokenRefreshed(newToken);
        return newToken;
      } else {
        // Refresh failed, redirect to login
        window.location.href = "/login";
        return null;
      }
    } catch (refreshError) {
      isRefreshing = false;
      console.error("Token refresh failed:", refreshError);
      authStorage.clear();
      window.location.href = "/login";
      return null;
    }
  } else if (!refreshToken) {
    // No refresh token available, redirect to login
    authStorage.clear();
    window.location.href = "/login";
    return null;
  }

  return null;
}
