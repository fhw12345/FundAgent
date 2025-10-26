/**
 * Chat history sidebar with glassmorphism design.
 * Displays list of user's chats with create new chat button.
 */

import { useState, memo } from "react";
import {
  Plus,
  Archive,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useChats, useDeleteChat } from "../../hooks/useChats";
import { ChatListItem } from "./ChatListItem";

interface ChatSidebarProps {
  activeChatId: string | null;
  onChatSelect: (chatId: string) => void;
  onNewChat: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const ChatSidebar = memo(function ChatSidebar({
  activeChatId,
  onChatSelect,
  onNewChat,
  isCollapsed,
  onToggleCollapse,
}: ChatSidebarProps) {
  const [showArchived, setShowArchived] = useState(false);

  // Fetch chats with React Query
  const { data, isLoading, isError, error } = useChats(1, 20, showArchived);

  // Delete mutation
  const { mutate: deleteChat } = useDeleteChat();

  const handleDeleteChat = (chatId: string) => {
    if (
      window.confirm(
        "Are you sure you want to delete this chat? This action cannot be undone.",
      )
    ) {
      deleteChat(chatId, {
        onSuccess: () => {
          // If deleted chat was active, clear selection
          if (chatId === activeChatId) {
            onNewChat();
          }
        },
        onError: (error) => {
          alert(
            `Failed to delete chat: ${error instanceof Error ? error.message : "Unknown error"}`,
          );
        },
      });
    }
  };

  // If collapsed, show minimal sidebar
  if (isCollapsed) {
    return (
      <aside className="w-12 h-full flex flex-col bg-gradient-to-b from-white/80 to-gray-50/80 backdrop-blur-xl border-r border-gray-200/50 items-center justify-center relative">
        <button
          onClick={onToggleCollapse}
          className="absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 text-white p-2.5 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 group hover:scale-110"
          title="Expand sidebar"
        >
          <ChevronRight
            size={20}
            strokeWidth={3.5}
            className="text-white"
          />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-full h-full flex flex-col bg-gradient-to-b from-white/80 to-gray-50/80 backdrop-blur-xl relative">
      {/* Collapse Button - Centered vertically on right edge */}
      <button
        onClick={onToggleCollapse}
        className="absolute right-0 top-1/2 translate-x-1/2 -translate-y-1/2 bg-gradient-to-r from-blue-500 to-indigo-500 hover:from-blue-600 hover:to-indigo-600 text-white p-2.5 rounded-full shadow-lg hover:shadow-xl transition-all duration-200 z-10 group hover:scale-110"
        title="Collapse sidebar"
      >
        <ChevronLeft
          size={20}
          strokeWidth={3.5}
          className="text-white"
        />
      </button>

      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/50">
        <h2 className="text-xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent mb-3">
          Chat History
        </h2>

        {/* New Chat Button */}
        <button
          onClick={onNewChat}
          className="w-full px-4 py-2.5 bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold rounded-xl shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 transition-all duration-200 flex items-center justify-center gap-2"
        >
          <Plus size={18} />
          New Chat
        </button>

        {/* Archive Toggle */}
        <button
          onClick={() => setShowArchived(!showArchived)}
          className={`
            w-full mt-2 px-4 py-2 text-sm font-medium rounded-lg transition-all
            ${
              showArchived
                ? "bg-blue-100/80 text-blue-700 border border-blue-200"
                : "bg-gray-100/80 text-gray-700 hover:bg-gray-200/80"
            }
            flex items-center justify-center gap-2
          `}
        >
          <Archive size={16} />
          {showArchived ? "Hide Archived" : "Show Archived"}
        </button>
      </div>

      {/* Chat List */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        {isLoading && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
          </div>
        )}

        {isError && (
          <div className="px-4 py-6 text-center">
            <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
            <p className="text-sm text-red-600 font-medium">
              Failed to load chats
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
          </div>
        )}

        {data && data.chats.length === 0 && (
          <div className="px-4 py-8 text-center">
            <p className="text-sm text-gray-500">
              {showArchived ? "No archived chats" : "No chats yet"}
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Start a new conversation to begin
            </p>
          </div>
        )}

        {data?.chats.map((chat) => (
          <ChatListItem
            key={chat.chat_id}
            chat={chat}
            isActive={chat.chat_id === activeChatId}
            onClick={() => onChatSelect(chat.chat_id)}
            onDelete={handleDeleteChat}
          />
        ))}
      </div>

      {/* Footer with count */}
      {data && data.total > 0 && (
        <div className="px-4 py-3 border-t border-gray-200/50">
          <p className="text-xs text-gray-500 text-center">
            {data.chats.length} of {data.total} chats
          </p>
        </div>
      )}
    </aside>
  );
});
