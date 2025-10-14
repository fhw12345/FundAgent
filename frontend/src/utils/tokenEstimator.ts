/**
 * Token Estimation Utility
 *
 * Provides rough estimates of token counts for cost calculation.
 * Uses approximation: ~4 characters per token (OpenAI's rule of thumb)
 */

export interface TokenEstimate {
  contextTokens: number;
  inputTokens: number;
  totalTokens: number;
  estimatedCredits: number;
}

// Cost constants (aligned with backend)
const CHARS_PER_TOKEN = 4; // Rough approximation
const TOKENS_PER_CREDIT = 200; // Backend constant: 200 tokens = 1 credit

// Estimate average output tokens (conservative estimate)
const ESTIMATED_OUTPUT_TOKENS = 500;

/**
 * Estimate token count from text
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  return Math.ceil(text.length / CHARS_PER_TOKEN);
}

/**
 * Calculate estimated cost for a chat message including context
 */
export function estimateChatCost(
  contextMessages: Array<{ role: string; content: string }>,
  inputMessage: string
): TokenEstimate {
  // Calculate context tokens (all previous messages)
  const contextTokens = contextMessages.reduce((total, msg) => {
    return total + estimateTokens(msg.content);
  }, 0);

  // Calculate input tokens (new message)
  const inputTokens = estimateTokens(inputMessage);

  // Total input tokens (context + new message)
  const totalInputTokens = contextTokens + inputTokens;

  // Total tokens (input + estimated output)
  const totalTokens = totalInputTokens + ESTIMATED_OUTPUT_TOKENS;

  // Calculate cost: total_tokens / 200 = credits
  const estimatedCredits = Math.ceil(totalTokens / TOKENS_PER_CREDIT);

  return {
    contextTokens,
    inputTokens,
    totalTokens,
    estimatedCredits,
  };
}
