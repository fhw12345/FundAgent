/**
 * Hook for fetching portfolio agent chat history.
 * Transforms portfolio API response to match chat structure.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface Message {
  message_id: string;
  chat_id: string;
  role: string;
  content: string;
  timestamp: string;
  metadata?: {
    symbol?: string;
    analysis_id?: string;
    trend_direction?: string;
  };
}

interface Chat {
  chat_id: string;
  title: string;
  user_id: string;
  created_at: string;
  updated_at: string;
  is_archived: boolean;
  last_message_preview?: string;
  last_message_at?: string;
}

interface ChatsResponse {
  chats: Chat[];
  total: number;
  page: number;
  page_size: number;
}

interface SymbolChat {
  chat_id: string;
  symbol: string;
  title: string;
  message_count: number;
  messages: Message[];
  latest_timestamp: string;
}

interface PortfolioChatHistoryResponse {
  chats: SymbolChat[];
}

async function fetchPortfolioChats(): Promise<ChatsResponse> {
  const response = await fetch(
    `${API_BASE_URL}/api/portfolio/chat-history`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch portfolio chats: ${response.statusText}`);
  }

  const data: PortfolioChatHistoryResponse = await response.json();

  // Transform to chat structure
  const chats: Chat[] = data.chats.map((symbolChat) => ({
    chat_id: symbolChat.chat_id,
    title: symbolChat.title,
    user_id: "portfolio_agent",
    created_at: symbolChat.latest_timestamp,
    updated_at: symbolChat.latest_timestamp,
    is_archived: false,
    last_message_preview: symbolChat.messages[symbolChat.messages.length - 1]?.content?.substring(0, 100) || "",
    last_message_at: symbolChat.latest_timestamp,
  }));

  return {
    chats,
    total: chats.length,
    page: 1,
    page_size: chats.length,
  };
}

export function usePortfolioChats() {
  return useQuery({
    queryKey: ["portfolio-chats"],
    queryFn: fetchPortfolioChats,
    refetchInterval: 30000, // Refetch every 30 seconds
  });
}

/**
 * Delete a portfolio agent chat.
 * Uses /api/portfolio/chats/{chatId} endpoint.
 */
async function deletePortfolioChat(chatId: string): Promise<void> {
  const response = await fetch(
    `${API_BASE_URL}/api/portfolio/chats/${chatId}`,
    {
      method: "DELETE",
      credentials: "include",
    }
  );

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || `Failed to delete portfolio chat: ${response.statusText}`);
  }
}

/**
 * Hook for deleting portfolio agent chats.
 */
export function useDeletePortfolioChat() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deletePortfolioChat,
    onSuccess: () => {
      // Invalidate portfolio chats query to refetch the list
      queryClient.invalidateQueries({ queryKey: ["portfolio-chats"] });
    },
  });
}
