import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Send, BarChart3, TrendingUp, DollarSign, Loader2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { chatService } from '../services/api'
import type { ChatMessage } from '../types/api'

export function ChatInterface() {
  const [message, setMessage] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content: `Hello! I'm your AI financial analysis assistant. I can help you with:

• **Fibonacci Analysis** - Technical retracement levels for any stock
• **Market Structure** - Swing points and trend analysis
• **Macro Analysis** - VIX, market sentiment, and sector rotation
• **Stock Fundamentals** - Company metrics and valuation data

Try asking something like "Show me Fibonacci analysis for AAPL" or click one of the quick actions below.`,
      timestamp: new Date().toISOString(),
    },
  ])

  const chatMutation = useMutation({
    mutationFn: chatService.sendMessage,
    onMutate: async (newMessage) => {
      // Optimistically add user message
      const userMessage: ChatMessage = {
        role: 'user',
        content: newMessage,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, userMessage])
      setMessage('')
      return { userMessage }
    },
    onSuccess: (response) => {
      // Add assistant response
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: response.response,
        timestamp: new Date().toISOString(),
        chart_url: response.chart_url,
        analysis_data: response.analysis_data,
      }
      setMessages(prev => [...prev, assistantMessage])
    },
    onError: (error) => {
      // Add error message
      const errorMessage: ChatMessage = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMessage])
    },
  })

  const handleSendMessage = () => {
    if (!message.trim()) return
    chatMutation.mutate(message)
  }

  const handleQuickAction = (action: string) => {
    chatMutation.mutate(action)
  }

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  return (
    <div className="bg-white rounded-lg shadow-sm border h-[600px] flex flex-col">
      {/* Chat Header */}
      <div className="border-b p-4">
        <h3 className="text-lg font-medium text-gray-900">Financial Analysis Chat</h3>
        <p className="text-sm text-gray-500">Ask me about stocks, market analysis, or financial data</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                msg.role === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <div className="markdown-content text-sm max-w-none">
                {msg.role === 'user' ? (
                  <p className="text-white m-0">{msg.content}</p>
                ) : (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                )}
              </div>

              {/* Chart Display */}
              {msg.chart_url && (
                <div className="mt-3">
                  <img
                    src={msg.chart_url}
                    alt="Financial Chart"
                    className="rounded-md border max-w-full h-auto"
                  />
                </div>
              )}

              {/* Analysis Data */}
              {msg.analysis_data && (
                <div className="mt-3 p-2 bg-gray-50 rounded text-xs">
                  <pre className="text-gray-600 overflow-x-auto">
                    {JSON.stringify(msg.analysis_data, null, 2)}
                  </pre>
                </div>
              )}

              <div
                className={`text-xs mt-1 ${
                  msg.role === 'user' ? 'text-blue-200' : 'text-gray-500'
                }`}
              >
                {formatTimestamp(msg.timestamp)}
              </div>
            </div>
          </div>
        ))}

        {/* Loading indicator */}
        {chatMutation.isPending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-4 py-2 rounded-lg">
              <div className="flex items-center space-x-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span className="text-sm text-gray-600">Analyzing...</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick Actions */}
      <div className="border-t p-4">
        <div className="mb-3">
          <p className="text-xs text-gray-500 mb-2">Quick Actions:</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleQuickAction('Show me Fibonacci analysis for AAPL')}
              disabled={chatMutation.isPending}
              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800 hover:bg-blue-200 disabled:opacity-50"
            >
              <BarChart3 className="h-3 w-3 mr-1" />
              Fibonacci AAPL
            </button>
            <button
              onClick={() => handleQuickAction('What is the current macro market sentiment?')}
              disabled={chatMutation.isPending}
              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 hover:bg-green-200 disabled:opacity-50"
            >
              <TrendingUp className="h-3 w-3 mr-1" />
              Macro Sentiment
            </button>
            <button
              onClick={() => handleQuickAction('Give me fundamental info for TSLA')}
              disabled={chatMutation.isPending}
              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800 hover:bg-purple-200 disabled:opacity-50"
            >
              <DollarSign className="h-3 w-3 mr-1" />
              Fundamentals TSLA
            </button>
          </div>
        </div>

        {/* Message Input */}
        <div className="flex space-x-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && handleSendMessage()}
            placeholder="Ask about stocks, Fibonacci analysis, market sentiment..."
            disabled={chatMutation.isPending}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={handleSendMessage}
            disabled={!message.trim() || chatMutation.isPending}
            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {chatMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  )
}