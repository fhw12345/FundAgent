/**
 * Token Estimation Utility
 *
 * Provides rough estimates of token counts for cost calculation.
 * Uses language-aware approximation:
 * - ASCII/Latin: ~4 characters per token (OpenAI's rule of thumb)
 * - CJK (Chinese/Japanese/Korean): ~1.5 characters per token
 */

export interface TokenEstimate {
  contextTokens: number;
  inputTokens: number;
  totalTokens: number;
  estimatedCredits: number;
}

// Cost constants (aligned with backend)
const CHARS_PER_TOKEN_LATIN = 4; // English, European languages
const CHARS_PER_TOKEN_CJK = 1.5; // Chinese, Japanese, Korean (more conservative)
const TOKENS_PER_CREDIT = 200; // Backend constant: 200 tokens = 1 credit

// Estimate average output tokens (conservative estimate)
const ESTIMATED_OUTPUT_TOKENS = 500;

/**
 * Check if character is CJK (Chinese, Japanese, Korean)
 * Unicode ranges:
 * - CJK Unified Ideographs: 4E00-9FFF
 * - Hiragana: 3040-309F
 * - Katakana: 30A0-30FF
 * - Hangul: AC00-D7AF
 */
function isCJKCharacter(char: string): boolean {
  const code = char.charCodeAt(0);
  return (
    (code >= 0x4e00 && code <= 0x9fff) || // CJK Unified Ideographs
    (code >= 0x3040 && code <= 0x309f) || // Hiragana
    (code >= 0x30a0 && code <= 0x30ff) || // Katakana
    (code >= 0xac00 && code <= 0xd7af) // Hangul
  );
}

/**
 * Estimate token count from text with language-aware logic
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;

  // Count CJK and non-CJK characters separately
  let cjkCharCount = 0;
  let latinCharCount = 0;

  for (let i = 0; i < text.length; i++) {
    if (isCJKCharacter(text[i])) {
      cjkCharCount++;
    } else {
      latinCharCount++;
    }
  }

  // Calculate tokens for each type
  const cjkTokens = Math.ceil(cjkCharCount / CHARS_PER_TOKEN_CJK);
  const latinTokens = Math.ceil(latinCharCount / CHARS_PER_TOKEN_LATIN);

  return cjkTokens + latinTokens;
}

/**
 * Calculate estimated cost for a chat message including context
 *
 * Examples:
 * - English text: "Hello world" (11 chars) → ~3 tokens
 * - Chinese text: "你好世界" (4 chars) → ~3 tokens
 * - Mixed text: "Hello 世界" (8 chars: 6 Latin + 2 CJK) → ~4 tokens
 *
 * Note: This is a rough estimation. Actual token counts from the LLM
 * may vary by ±20% depending on tokenization algorithm.
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
