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
import { useChats } from "../../hooks/useChats";
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

  // If collapsed, show minimal sidebar
  if (isCollapsed) {
    return (
      <aside className="w-12 h-full flex flex-col bg-gradient-to-b from-white/80 to-gray-50/80 backdrop-blur-xl border-r border-gray-200/50 items-center py-4">
        <button
          onClick={onToggleCollapse}
          className="p-2 hover:bg-gray-100/80 rounded-lg transition-all group"
          title="Expand sidebar"
        >
          <ChevronRight
            size={20}
            className="text-gray-600 group-hover:text-gray-900"
          />
        </button>
      </aside>
    );
  }

  return (
    <aside className="w-80 h-full flex flex-col bg-gradient-to-b from-white/80 to-gray-50/80 backdrop-blur-xl border-r border-gray-200/50 relative">
      {/* Collapse Button */}
      <button
        onClick={onToggleCollapse}
        className="absolute top-4 right-2 p-1.5 hover:bg-gray-100/80 rounded-lg transition-all z-10 group"
        title="Collapse sidebar"
      >
        <ChevronLeft
          size={18}
          className="text-gray-500 group-hover:text-gray-900"
        />
      </button>

      {/* Header */}
      <div className="px-4 py-4 border-b border-gray-200/50">
        <h2 className="text-lg font-bold text-gray-900 mb-3 flex items-center gap-2">
          <span className="text-xl">💬</span>
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
