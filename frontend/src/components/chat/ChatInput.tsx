/**
 * ChatInput Component
 *
 * Provides a text input field and a send button for users to interact with the chatbot.
 */

import React from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  message: string
  setMessage: (message: string) => void
  onSendMessage: () => void
  isPending: boolean
  currentSymbol: string | null
}

export const ChatInput: React.FC<ChatInputProps> = ({ message, setMessage, onSendMessage, isPending, currentSymbol }) => {
  return (
    <div className="border-t p-4">
      <div className="flex gap-2">
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && onSendMessage()}
          placeholder={currentSymbol ?
            `Ask about ${currentSymbol} or request analysis...` :
            "Ask questions or search for a symbol on the right..."
          }
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          disabled={isPending}
        />
        <button
          onClick={onSendMessage}
          disabled={!message.trim() || isPending}
          className="bg-blue-500 text-white p-2 rounded-lg hover:bg-blue-600 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}