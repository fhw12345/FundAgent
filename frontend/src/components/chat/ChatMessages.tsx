/**
 * ChatMessages Component
 *
 * Renders the list of chat messages, including user messages,
 * assistant responses, and loading indicators.
 */

import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loader2 } from "lucide-react";
import type { ChatMessage } from "../../types/api";

interface ChatMessagesProps {
  messages: ChatMessage[];
  isAnalysisPending: boolean;
}

const formatTimestamp = (timestamp: string) => {
  return new Date(timestamp).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
};

// Memoized message component to prevent re-renders
const MessageBubble = React.memo<{ msg: ChatMessage }>(({ msg }) => (
  <div
    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
  >
    <div
      className={`px-6 py-4 rounded-xl ${
        msg.role === "user"
          ? "max-w-full lg:max-w-4xl bg-white text-gray-900 border-2 border-blue-500/30 shadow-sm"
          : "max-w-full lg:max-w-3xl mr-8 bg-gray-50 text-gray-900 border border-gray-200"
      }`}
    >
      <div className="markdown-content text-base max-w-none">
        {msg.role === "user" ? (
          <p className="text-base">{msg.content}</p>
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              h1: ({ children }) => (
                <h1 className="text-xl font-bold mb-3 text-gray-900">
                  {children}
                </h1>
              ),
              h2: ({ children }) => (
                <h2 className="text-lg font-bold mb-3 text-gray-900">
                  {children}
                </h2>
              ),
              h3: ({ children }) => (
                <h3 className="text-base font-bold mb-2 text-gray-800">
                  {children}
                </h3>
              ),
              p: ({ children }) => (
                <p className="mb-3 last:mb-0 leading-relaxed text-base">
                  {children}
                </p>
              ),
              ul: ({ children }) => (
                <ul className="list-disc list-inside mb-3 space-y-2 ml-2">
                  {children}
                </ul>
              ),
              ol: ({ children }) => (
                <ol className="list-decimal list-inside mb-3 space-y-2 ml-2">
                  {children}
                </ol>
              ),
              li: ({ children }) => (
                <li className="text-base leading-relaxed">{children}</li>
              ),
              strong: ({ children }) => (
                <strong className="font-semibold text-gray-900">
                  {children}
                </strong>
              ),
              code: ({ className, children, ...props }) => {
                const isInline = !className;
                return isInline ? (
                  <code
                    className="bg-blue-100 text-blue-800 px-1.5 py-0.5 rounded text-sm font-mono"
                    {...props}
                  >
                    {children}
                  </code>
                ) : (
                  <code
                    className={`block bg-gray-800 text-gray-100 p-3 rounded text-sm font-mono overflow-x-auto ${className}`}
                    {...props}
                  >
                    {children}
                  </code>
                );
              },
              pre: ({ children }) => (
                <pre className="mb-3 rounded overflow-hidden">{children}</pre>
              ),
              blockquote: ({ children }) => (
                <blockquote className="border-l-4 border-blue-500 pl-4 my-3 italic text-gray-700">
                  {children}
                </blockquote>
              ),
            }}
          >
            {msg.content}
          </ReactMarkdown>
        )}
      </div>
      <div className="text-xs opacity-70 mt-1">
        {formatTimestamp(msg.timestamp)}
      </div>
    </div>
  </div>
));

export const ChatMessages: React.FC<ChatMessagesProps> = ({
  messages,
  isAnalysisPending,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isAnalysisPending]);

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
      {messages.map((msg: any) => (
        <MessageBubble key={msg._id || msg.timestamp} msg={msg} />
      ))}

      {isAnalysisPending && (
        <div className="flex justify-start">
          <div className="bg-gray-50 text-gray-900 px-6 py-3 rounded-xl border border-gray-200">
            <div className="flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
              <span className="text-sm font-medium">Analyzing...</span>
            </div>
          </div>
        </div>
      )}

      {/* Invisible scroll target */}
      <div ref={messagesEndRef} />
    </div>
  );
};
