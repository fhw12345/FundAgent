/**
 * ChatInput Component
 *
 * Provides a text input field and a send button for users to interact with the chatbot.
 * Shows cost estimation and low balance warnings.
 */

import React, { useMemo } from "react";
import { Send, AlertCircle, Coins } from "lucide-react";
import { useCurrentBalance } from "../../hooks/useCredits";
import { estimateChatCost } from "../../utils/tokenEstimator";

interface ChatInputProps {
  message: string;
  setMessage: (message: string) => void;
  onSendMessage: () => void;
  isPending: boolean;
  currentSymbol: string | null;
  messages: Array<{ role: string; content: string }>;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  message,
  setMessage,
  onSendMessage,
  isPending,
  currentSymbol,
  messages,
}) => {
  const currentBalance = useCurrentBalance();

  // Calculate estimated cost based on context + input
  const costEstimate = useMemo(() => {
    if (!message.trim()) return { estimatedCredits: 0 };
    return estimateChatCost(messages, message);
  }, [messages, message]);

  const estimatedCost = costEstimate.estimatedCredits;

  const hasInsufficientCredits =
    currentBalance !== null && currentBalance < estimatedCost;
  const isLowBalance =
    currentBalance !== null &&
    currentBalance < 50 &&
    currentBalance >= estimatedCost;

  return (
    <div className="border-t border-gray-200 px-6 py-4 bg-white">
      {/* Warning Banner */}
      {hasInsufficientCredits && (
        <div className="mb-3 px-4 py-3 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
          <AlertCircle size={20} className="text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-semibold text-red-800">
              Insufficient Credits
            </p>
            <p className="text-xs text-red-600 mt-0.5">
              You need at least {estimatedCost} credits to send this message.
              Current balance: {currentBalance?.toFixed(1) ?? "Loading..."}{" "}
              credits
            </p>
          </div>
        </div>
      )}

      {isLowBalance && (
        <div className="mb-3 px-4 py-3 bg-orange-50 border border-orange-200 rounded-xl flex items-start gap-3">
          <AlertCircle
            size={20}
            className="text-orange-600 flex-shrink-0 mt-0.5"
          />
          <div className="flex-1">
            <p className="text-sm font-semibold text-orange-800">
              Low Credit Balance
            </p>
            <p className="text-xs text-orange-600 mt-0.5">
              You have {currentBalance?.toFixed(1)} credits remaining. Consider
              topping up soon.
            </p>
          </div>
        </div>
      )}

      <div className="flex gap-3">
        <div className="flex-1">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !hasInsufficientCredits) {
                onSendMessage();
              }
            }}
            placeholder={
              currentSymbol
                ? `Ask about ${currentSymbol} or request analysis...`
                : "Ask questions or search for a symbol on the right..."
            }
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
            disabled={isPending || hasInsufficientCredits}
          />
          {/* Cost Estimation */}
          {message.trim() && !hasInsufficientCredits && (
            <div className="flex items-center gap-1 mt-2 text-xs text-gray-500">
              <Coins size={12} />
              <span>
                Estimated cost: ~{estimatedCost} credits ({costEstimate.contextTokens}{" "}
                context + {costEstimate.inputTokens} input tokens)
              </span>
            </div>
          )}
        </div>
        <button
          onClick={onSendMessage}
          disabled={!message.trim() || isPending || hasInsufficientCredits}
          className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-5 py-3 rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
          title={
            hasInsufficientCredits
              ? "Insufficient credits"
              : "Send message (Enter)"
          }
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
};
