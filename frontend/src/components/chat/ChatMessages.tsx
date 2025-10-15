/**
 * ChatMessages Component
 *
 * Renders the list of chat messages, including user messages,
 * assistant responses, and loading indicators.
 */

import React, { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
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

// Parse thinking content from message
const parseThinkingContent = (content: string): { thinking: string[]; mainContent: string } => {
  const thinkingRegex = /<thinking>(.*?)<\/thinking>/gs;
  const thinkingMatches: string[] = [];
  let match;

  while ((match = thinkingRegex.exec(content)) !== null) {
    thinkingMatches.push(match[1]);
  }

  // Remove thinking tags from main content
  const mainContent = content.replace(thinkingRegex, '').trim();

  return {
    thinking: thinkingMatches,
    mainContent: mainContent || content, // Fallback to original if empty
  };
};

// Memoized message component to prevent re-renders
const MessageBubble = React.memo<{ msg: ChatMessage }>(({ msg }) => {
  const { thinking, mainContent } = msg.role === "assistant"
    ? parseThinkingContent(msg.content)
    : { thinking: [], mainContent: msg.content };

  return (
    <div
      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`px-6 py-4 rounded-xl ${
          msg.role === "user"
            ? "max-w-full lg:max-w-4xl bg-white text-gray-900 border-2 border-blue-500/30 shadow-sm"
            : "w-full bg-gray-50 text-gray-900 border border-gray-200"
        }`}
      >
        {/* Thinking Content (Collapsible) */}
        {thinking.length > 0 && (
          <details className="mb-4 border border-blue-300 rounded-lg p-3 bg-blue-50">
            <summary className="cursor-pointer font-medium text-blue-700 hover:text-blue-900 select-none flex items-center gap-2">
              <span>🤔 Thinking Process</span>
              <span className="text-xs text-blue-600">({thinking.join('').length} characters)</span>
            </summary>
            <div className="mt-3 text-sm text-gray-700 whitespace-pre-wrap font-mono bg-white p-3 rounded border border-blue-200">
              {thinking.join('\n\n')}
            </div>
          </details>
        )}

        <div className="markdown-content text-base max-w-none">
          {msg.role === "user" ? (
            <p className="text-base">{msg.content}</p>
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeRaw]}
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
                table: ({ children, style }) => (
                  <div className="overflow-x-auto mb-3">
                    <table
                      style={style}
                      className="min-w-full border-collapse border border-gray-300"
                    >
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children, style }) => (
                  <thead style={style} className="bg-gray-100">
                    {children}
                  </thead>
                ),
                tbody: ({ children, style }) => (
                  <tbody style={style}>{children}</tbody>
                ),
                tr: ({ children, style }) => (
                  <tr style={style} className="border-b border-gray-300">
                    {children}
                  </tr>
                ),
                th: ({ children, style }) => (
                  <th
                    style={style}
                    className="px-4 py-2 text-left font-semibold text-gray-900 border-r border-gray-300 last:border-r-0"
                  >
                    {children}
                  </th>
                ),
                td: ({ children, style }) => (
                  <td
                    style={style}
                    className="px-4 py-2 text-gray-800 border-r border-gray-300 last:border-r-0"
                  >
                    {children}
                  </td>
                ),
                // HTML elements for collapsible sections
                details: ({ children }) => (
                  <details className="my-3 border border-gray-300 rounded-lg p-3 bg-gray-50">
                    {children}
                  </details>
                ),
                summary: ({ children }) => (
                  <summary className="cursor-pointer font-medium text-blue-700 hover:text-blue-900 select-none">
                    {children}
                  </summary>
                ),
              }}
            >
              {mainContent}
            </ReactMarkdown>
          )}
        </div>
        <div className="text-xs opacity-70 mt-1">
          {formatTimestamp(msg.timestamp)}
        </div>
      </div>
    </div>
  );
});

MessageBubble.displayName = "MessageBubble";

export const ChatMessages: React.FC<ChatMessagesProps> = ({
  messages,
  isAnalysisPending,
}) => {
  const lastUserMessageRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const lastScrolledUserMessageRef = useRef<string | null>(null);

  // Scroll ONCE when new user message appears, then let user control scroll
  useEffect(() => {
    // Find the last user message
    const lastUserMessage = [...messages]
      .reverse()
      .find((msg) => msg.role === "user");

    if (!lastUserMessage) {
      // No user messages yet - scroll to bottom for initial load
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      return;
    }

    // Generate unique ID for this user message
    const userMessageId = String(
      lastUserMessage._id || lastUserMessage.timestamp,
    );

    // Only scroll if this is a NEW user message (haven't scrolled to it yet)
    if (lastScrolledUserMessageRef.current !== userMessageId) {
      lastUserMessageRef.current?.scrollIntoView({ behavior: "smooth" });
      lastScrolledUserMessageRef.current = userMessageId;
    }
    // During streaming: don't scroll - user has control
  }, [messages]);

  // Find last user message index once (used for ref attachment)
  let lastUserIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === "user") {
      lastUserIdx = i;
      break;
    }
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
      {messages.map((msg: any, index: number) => {
        const isLastUserMessage = msg.role === "user" && index === lastUserIdx;

        return (
          <div
            key={msg._id || msg.timestamp}
            ref={isLastUserMessage ? lastUserMessageRef : null}
          >
            <MessageBubble msg={msg} />
          </div>
        );
      })}

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

      {/* Invisible scroll target for bottom */}
      <div ref={messagesEndRef} />
    </div>
  );
};
