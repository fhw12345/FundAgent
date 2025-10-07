/**
 * React Query hooks for persistent chat management.
 * Handles chat list, chat detail, and UI state updates.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  Chat,
  ChatListResponse,
  ChatDetailResponse,
  UpdateUIStateRequest,
} from "../types/api";
import { chatService } from "../services/api";

// ===== Query Keys =====

export const chatKeys = {
  all: ["chats"] as const,
  lists: () => [...chatKeys.all, "list"] as const,
  list: (page: number, includeArchived: boolean) =>
    [...chatKeys.lists(), { page, includeArchived }] as const,
  details: () => [...chatKeys.all, "detail"] as const,
  detail: (chatId: string) => [...chatKeys.details(), chatId] as const,
};

// ===== Hooks =====

/**
 * Hook to fetch list of chats with pagination
 */
export function useChats(
  page: number = 1,
  pageSize: number = 20,
  includeArchived: boolean = false,
) {
  return useQuery({
    queryKey: chatKeys.list(page, includeArchived),
    queryFn: () => chatService.listChats(page, pageSize, includeArchived),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  });
}

/**
 * Hook to fetch chat detail with messages
 */
export function useChatDetail(chatId: string | null, limit?: number) {
  return useQuery({
    queryKey: chatId ? chatKeys.detail(chatId) : [],
    queryFn: () => {
      if (!chatId) throw new Error("Chat ID is required");
      return chatService.getChatDetail(chatId, limit);
    },
    enabled: !!chatId, // Only fetch if chatId exists
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchOnMount: false, // Prevent refetch on component mount
    refetchOnWindowFocus: false, // Prevent refetch on window focus
    refetchOnReconnect: false, // Prevent refetch on reconnect
  });
}

/**
 * Hook to update chat UI state with optimistic updates
 */
export function useUpdateUIState() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      chatId,
      uiState,
    }: {
      chatId: string;
      uiState: UpdateUIStateRequest;
    }) => chatService.updateUIState(chatId, uiState),

    // Optimistic update
    onMutate: async ({ chatId, uiState }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: chatKeys.detail(chatId) });

      // Snapshot previous value
      const previousChatDetail = queryClient.getQueryData<ChatDetailResponse>(
        chatKeys.detail(chatId),
      );

      // Optimistically update
      if (previousChatDetail) {
        queryClient.setQueryData<ChatDetailResponse>(chatKeys.detail(chatId), {
          ...previousChatDetail,
          chat: {
            ...previousChatDetail.chat,
            ui_state: uiState.ui_state,
          },
        });
      }

      return { previousChatDetail };
    },

    // On error, rollback to previous value
    onError: (_err, { chatId }, context) => {
      if (context?.previousChatDetail) {
        queryClient.setQueryData(
          chatKeys.detail(chatId),
          context.previousChatDetail,
        );
      }
    },

    // Always refetch after error or success
    onSettled: (_data, _error, { chatId }) => {
      queryClient.invalidateQueries({ queryKey: chatKeys.detail(chatId) });
    },
  });
}

/**
 * Hook to invalidate chat list (for when new chat is created)
 */
export function useInvalidateChats() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
  };
}

/**
 * Hook to add new chat to cache optimistically
 */
export function useOptimisticChatAdd() {
  const queryClient = useQueryClient();

  return (newChat: Chat) => {
    // Get current chat list from cache
    const currentPage = 1;
    const includeArchived = false;
    const queryKey = chatKeys.list(currentPage, includeArchived);

    const previousData = queryClient.getQueryData<ChatListResponse>(queryKey);

    if (previousData) {
      // Add new chat to the beginning of the list
      queryClient.setQueryData<ChatListResponse>(queryKey, {
        ...previousData,
        chats: [newChat, ...previousData.chats],
        total: previousData.total + 1,
      });
    }

    // Invalidate to ensure fresh data
    queryClient.invalidateQueries({ queryKey: chatKeys.lists() });
  };
}

/**
 * Hook to update chat title in cache
 */
export function useUpdateChatTitle() {
  const queryClient = useQueryClient();

  return (chatId: string, newTitle: string) => {
    // Update in chat detail cache
    const detailQueryKey = chatKeys.detail(chatId);
    const previousDetail =
      queryClient.getQueryData<ChatDetailResponse>(detailQueryKey);

    if (previousDetail) {
      queryClient.setQueryData<ChatDetailResponse>(detailQueryKey, {
        ...previousDetail,
        chat: {
          ...previousDetail.chat,
          title: newTitle,
        },
      });
    }

    // Update in chat list cache (all pages)
    queryClient.setQueriesData<ChatListResponse>(
      { queryKey: chatKeys.lists() },
      (oldData) => {
        if (!oldData) return oldData;

        return {
          ...oldData,
          chats: oldData.chats.map((chat) =>
            chat.chat_id === chatId ? { ...chat, title: newTitle } : chat,
          ),
        };
      },
    );
  };
}
