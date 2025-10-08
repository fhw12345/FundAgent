/**
 * Chat Message Input - Message input field with send button
 */

import { Send, Loader2 } from "lucide-react";

interface ChatMessageInputProps {
  message: string;
  onMessageChange: (message: string) => void;
  onSend: () => void;
  disabled: boolean;
  loading: boolean;
}

export function ChatMessageInput({
  message,
  onMessageChange,
  onSend,
  disabled,
  loading,
}: ChatMessageInputProps) {
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      onSend();
    }
  };

  return (
    <div className="flex space-x-2">
      <input
        type="text"
        value={message}
        onChange={(e) => onMessageChange(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Ask about stocks, Fibonacci analysis, market sentiment..."
        disabled={disabled}
        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
      />
      <button
        onClick={onSend}
        disabled={!message.trim() || disabled}
        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Send className="h-4 w-4" />
        )}
      </button>
    </div>
  );
}
