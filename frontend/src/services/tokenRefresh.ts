/**
 * Token refresh interceptor logic for axios
 * Handles automatic access token refresh before expiry
 */

import type { AxiosRequestConfig } from "axios";

// Token refresh state
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
 * Refresh access token if expiring soon (< 5 minutes)
 * Returns updated config with new token
 */
export async function refreshTokenIfNeeded(
  config: AxiosRequestConfig,
): Promise<AxiosRequestConfig> {
  const accessToken = localStorage.getItem("access_token");
  const refreshToken = localStorage.getItem("refresh_token");
  const expiry = localStorage.getItem("access_token_expiry");

  if (accessToken && refreshToken && expiry) {
    const expiryTime = parseInt(expiry, 10);
    const now = Date.now();
    const fiveMinutes = 5 * 60 * 1000;

    // If token expires in less than 5 minutes, refresh it
    if (now > expiryTime - fiveMinutes) {
      if (!isRefreshing) {
        isRefreshing = true;

        try {
          const response = await fetch(
            `${config.baseURL || ""}/api/auth/refresh`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                refresh_token: refreshToken,
              }),
            },
          );

          if (response.ok) {
            const data = await response.json();
            localStorage.setItem("access_token", data.access_token);
            localStorage.setItem("refresh_token", data.refresh_token);
            const newExpiry = Date.now() + data.expires_in * 1000;
            localStorage.setItem("access_token_expiry", newExpiry.toString());

            isRefreshing = false;
            onTokenRefreshed(data.access_token);

            if (config.headers) {
              config.headers.Authorization = `Bearer ${data.access_token}`;
            }
          } else {
            // Refresh failed, clear tokens
            isRefreshing = false;
            localStorage.removeItem("access_token");
            localStorage.removeItem("refresh_token");
            localStorage.removeItem("access_token_expiry");
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
 */
export async function retryWithRefreshToken(
  originalRequest: AxiosRequestConfig,
): Promise<Response | null> {
  const refreshToken = localStorage.getItem("refresh_token");

  if (refreshToken && !isRefreshing) {
    isRefreshing = true;

    try {
      const response = await fetch(
        `${originalRequest.baseURL || ""}/api/auth/refresh`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            refresh_token: refreshToken,
          }),
        },
      );

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        const newExpiry = Date.now() + data.expires_in * 1000;
        localStorage.setItem("access_token_expiry", newExpiry.toString());

        isRefreshing = false;
        onTokenRefreshed(data.access_token);

        return data.access_token;
      } else {
        // Refresh failed
        isRefreshing = false;
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("access_token_expiry");
        window.location.href = "/login";
        return null;
      }
    } catch (refreshError) {
      isRefreshing = false;
      console.error("Token refresh failed:", refreshError);
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("access_token_expiry");
      window.location.href = "/login";
      return null;
    }
  } else if (!refreshToken) {
    // No refresh token available, redirect to login
    localStorage.removeItem("access_token");
    localStorage.removeItem("access_token_expiry");
    window.location.href = "/login";
    return null;
  }

  return null;
}
