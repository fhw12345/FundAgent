import axios from "axios";
import type {
  HealthResponse,
  ChatRequest,
  ChatResponse,
  ChatListResponse,
  ChatDetailResponse,
  UpdateUIStateRequest,
  Chat,
  StreamEvent,
} from "../types/api";
import { refreshTokenIfNeeded, retryWithRefreshToken } from "./tokenRefresh";

// Configure axios with base URL
// In production, use empty string for relative URLs (nginx proxy)
// In development, use localhost
const api = axios.create({
  baseURL:
    import.meta.env.VITE_API_URL !== undefined
      ? import.meta.env.VITE_API_URL
      : import.meta.env.MODE === "production"
        ? ""
        : "http://localhost:8000",
  timeout: 30000, // 30 seconds for analysis requests
  headers: {
    "Content-Type": "application/json",
  },
});

// Export the configured axios instance for use in other services
export const apiClient = api;

// Request interceptor for authentication with auto-refresh
api.interceptors.request.use(
  async (config) => {
    return await refreshTokenIfNeeded(config);
  },
  (error) => {
    return Promise.reject(error);
  },
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      const newToken = await retryWithRefreshToken(originalRequest);

      if (newToken) {
        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      }
    }

    return Promise.reject(error);
  },
);

// Health service
export const healthService = {
  async getHealth(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>("/api/health");
    return response.data;
  },

  async getMongoHealth(): Promise<{
    connected: boolean;
    [key: string]: unknown;
  }> {
    const response = await api.get("/api/health/mongodb");
    return response.data;
  },

  async getRedisHealth(): Promise<{
    connected: boolean;
    [key: string]: unknown;
  }> {
    const response = await api.get("/api/health/redis");
    return response.data;
  },

  async getReadiness(): Promise<{ ready: boolean; [key: string]: unknown }> {
    const response = await api.get("/api/health/ready");
    return response.data;
  },

  async getLiveness(): Promise<{ alive: boolean; [key: string]: unknown }> {
    const response = await api.get("/api/health/live");
    return response.data;
  },
};

// Chat service
export const chatService = {
  async createSession(): Promise<{ session_id: string; created_at: string }> {
    const response = await api.post("/api/chat/sessions");
    return response.data;
  },

  async sendMessage(
    message: string,
    sessionId?: string,
  ): Promise<ChatResponse> {
    const request: ChatRequest = {
      message,
      session_id: sessionId,
    };

    const response = await api.post<ChatResponse>("/api/chat", request, {
      timeout: 60000, // 60 seconds for LLM responses (longer than default)
    });
    return response.data;
  },

  async getSessionInfo(sessionId: string): Promise<{
    session_id: string;
    message_count: number;
    created_at: string;
    updated_at: string;
    current_symbol: string | null;
  }> {
    const response = await api.get(`/api/chat/sessions/${sessionId}`);
    return response.data;
  },

  async deleteSession(
    sessionId: string,
  ): Promise<{ status: string; session_id: string }> {
    const response = await api.delete(`/api/chat/sessions/${sessionId}`);
    return response.data;
  },

  async addContextToSession(
    sessionId: string,
    content: string,
  ): Promise<{ status: string; session_id: string; message_count: number }> {
    const response = await api.post(`/api/chat/sessions/${sessionId}/context`, {
      content,
      session_id: sessionId,
    });
    return response.data;
  },

  /**
   * Send message with streaming response using EventSource (Server-Sent Events)
   *
   * @param message User message
   * @param sessionId Optional session ID
   * @param onChunk Callback for each content chunk
   * @param onSessionCreated Callback when session is created
   * @param onDone Callback when streaming completes
   * @param onError Callback for errors
   */
  sendMessageStream(
    message: string,
    sessionId: string | null,
    onChunk: (content: string) => void,
    onSessionCreated?: (sessionId: string) => void,
    onDone?: (sessionId: string, messageCount: number) => void,
    onError?: (error: string) => void,
  ): () => void {
    const baseURL =
      import.meta.env.VITE_API_URL !== undefined
        ? import.meta.env.VITE_API_URL
        : import.meta.env.MODE === "production"
          ? ""
          : "http://localhost:8000";

    // EventSource doesn't support POST, so we use POST via fetch to initiate,
    // then use EventSource with a session token if needed
    // For simplicity with SSE + POST body, we'll stick with fetch but use a cleaner approach

    // Actually, let's use fetch with ReadableStream but process it like EventSource
    const url = `${baseURL}/api/chat/stream`;

    const controller = new AbortController();

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("access_token")
          ? { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
          : {}),
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Response body is not readable");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          // Decode chunk and add to buffer
          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE messages (delimited by \n\n)
          const messages = buffer.split("\n\n");
          buffer = messages.pop() || ""; // Keep incomplete message in buffer

          for (const message of messages) {
            if (message.startsWith("data: ")) {
              const data = JSON.parse(message.slice(6));

              if (data.type === "session_created" && onSessionCreated) {
                onSessionCreated(data.session_id);
              } else if (data.type === "content") {
                onChunk(data.content);
                // Yield to browser to paint (important for real-time streaming)
                await new Promise((resolve) => setTimeout(resolve, 0));
              } else if (data.type === "done" && onDone) {
                onDone(data.session_id, data.message_count);
              } else if (data.type === "error" && onError) {
                console.error("SSE error:", data.error);
                onError(data.error);
              }
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== "AbortError") {
          if (onError) {
            onError(
              error instanceof Error
                ? error.message
                : "Unknown streaming error",
            );
          }
        }
      });

    // Return cleanup function
    return () => {
      controller.abort();
    };
  },

  // ===== Persistent Chat API =====

  /**
   * List all chats for the authenticated user
   */
  async listChats(
    page: number = 1,
    pageSize: number = 20,
    includeArchived: boolean = false,
  ): Promise<ChatListResponse> {
    const response = await api.get<ChatListResponse>("/api/chat/chats", {
      params: {
        page,
        page_size: pageSize,
        include_archived: includeArchived,
      },
    });
    return response.data;
  },

  /**
   * Get chat detail with messages for state restoration
   */
  async getChatDetail(
    chatId: string,
    limit?: number,
  ): Promise<ChatDetailResponse> {
    const response = await api.get<ChatDetailResponse>(
      `/api/chat/chats/${chatId}`,
      {
        params: limit ? { limit } : {},
      },
    );
    return response.data;
  },

  /**
   * Update chat UI state (debounced from frontend)
   */
  async updateUIState(
    chatId: string,
    request: UpdateUIStateRequest,
  ): Promise<Chat> {
    const response = await api.patch<Chat>(
      `/api/chat/chats/${chatId}/ui-state`,
      request,
    );
    return response.data;
  },

  /**
   * Delete a chat and all its messages
   */
  async deleteChat(chatId: string): Promise<void> {
    await api.delete(`/api/chat/chats/${chatId}`);
  },

  /**
   * Send message with streaming response and MongoDB persistence
   *
   * @param message User message
   * @param chatId Optional chat ID (creates new chat if not provided)
   * @param onChunk Callback for each content chunk
   * @param onChatCreated Callback when new chat is created
   * @param onTitleGenerated Callback when title is generated
   * @param onDone Callback when streaming completes
   * @param onError Callback for errors
   */
  sendMessageStreamPersistent(
    message: string,
    chatId: string | null,
    onChunk: (content: string) => void,
    onChatCreated?: (chatId: string) => void,
    onTitleGenerated?: (title: string) => void,
    onDone?: (chatId: string, messageCount: number) => void,
    onError?: (error: string) => void,
    options?: {
      title?: string;
      role?: string;
      source?: string;
      metadata?: any; // Analysis metadata for overlays
    },
  ): () => void {
    const baseURL =
      import.meta.env.VITE_API_URL !== undefined
        ? import.meta.env.VITE_API_URL
        : import.meta.env.MODE === "production"
          ? ""
          : "http://localhost:8000";

    const url = `${baseURL}/api/chat/stream-v2`;
    const controller = new AbortController();

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(localStorage.getItem("access_token")
          ? { Authorization: `Bearer ${localStorage.getItem("access_token")}` }
          : {}),
      },
      body: JSON.stringify({
        message,
        chat_id: chatId,
        title: options?.title,
        role: options?.role ?? "user",
        source: options?.source ?? "user",
        metadata: options?.metadata,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Response body is not readable");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            break;
          }

          buffer += decoder.decode(value, { stream: true });
          const messages = buffer.split("\n\n");
          buffer = messages.pop() || "";

          for (const message of messages) {
            if (message.startsWith("data: ")) {
              const data: StreamEvent = JSON.parse(message.slice(6));

              if (
                data.type === "chat_created" &&
                onChatCreated &&
                data.chat_id
              ) {
                onChatCreated(data.chat_id);
              } else if (data.type === "content" && data.content) {
                onChunk(data.content);
                await new Promise((resolve) => setTimeout(resolve, 0));
              } else if (
                data.type === "title_generated" &&
                onTitleGenerated &&
                data.title
              ) {
                onTitleGenerated(data.title);
              } else if (data.type === "done" && onDone && data.chat_id) {
                onDone(data.chat_id, data.message_count || 0);
              } else if (data.type === "error" && onError) {
                console.error("SSE error:", data.error);
                onError(data.error || "Unknown error");
              }
            }
          }
        }
      })
      .catch((error) => {
        if (error.name !== "AbortError" && onError) {
          onError(
            error instanceof Error ? error.message : "Unknown streaming error",
          );
        }
      });

    return () => {
      controller.abort();
    };
  },
};

// Analysis service (future implementation)
export const analysisService = {
  async getFibonacci(symbol: string, timeframe: string = "6mo") {
    const response = await api.post("/api/analysis/fibonacci", {
      symbol,
      timeframe,
    });
    return response.data;
  },

  async getMacroSentiment() {
    const response = await api.get("/api/analysis/macro");
    return response.data;
  },

  async getMarketStructure(symbol: string, timeframe: string = "6mo") {
    const response = await api.post("/api/analysis/market-structure", {
      symbol,
      timeframe,
    });
    return response.data;
  },

  async getFundamentals(symbol: string) {
    const response = await api.get(`/api/analysis/fundamentals/${symbol}`);
    return response.data;
  },
};
