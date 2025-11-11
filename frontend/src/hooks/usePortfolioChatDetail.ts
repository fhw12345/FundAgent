/**
 * React Query hook for fetching portfolio agent chat details.
 * Uses the /api/portfolio/chats/{chat_id} endpoint which doesn't require ownership.
 */

import { useQuery } from "@tanstack/react-query";
import type { ChatMessage, Chat } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface PortfolioChatDetailResponse {
  chat: Chat;
  messages: ChatMessage[];
}

/**
 * Fetch portfolio agent chat detail from API
 */
async function fetchPortfolioChatDetail(chatId: string): Promise<PortfolioChatDetailResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/portfolio/chats/${chatId}`,
    {
      credentials: "include", // Include cookies for authentication
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch portfolio chat: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Hook to fetch portfolio agent chat detail with messages
 */
export function usePortfolioChatDetail(chatId: string | null) {
  return useQuery({
    queryKey: chatId ? ["portfolio-chat", chatId] : [],
    queryFn: () => {
      if (!chatId) {
        throw new Error("Chat ID is required");
      }
      return fetchPortfolioChatDetail(chatId);
    },
    enabled: !!chatId, // Only fetch when chatId is provided
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });
}
