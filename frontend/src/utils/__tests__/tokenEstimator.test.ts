/**
 * Tests for token estimation with language-aware logic
 */

import { estimateTokens, estimateChatCost } from "../tokenEstimator";

describe("Token Estimation", () => {
  describe("estimateTokens", () => {
    it("should estimate tokens for English text", () => {
      const text = "Hello world, this is a test message!"; // 36 chars
      const tokens = estimateTokens(text);

      // ~36 / 4 = 9 tokens
      expect(tokens).toBeGreaterThanOrEqual(8);
      expect(tokens).toBeLessThanOrEqual(10);
    });

    it("should estimate tokens for Chinese text", () => {
      const text = "你好世界，这是一个测试消息！"; // 15 chars
      const tokens = estimateTokens(text);

      // ~15 / 1.5 = 10 tokens (CJK uses ~1.5 chars/token)
      expect(tokens).toBeGreaterThanOrEqual(9);
      expect(tokens).toBeLessThanOrEqual(11);
    });

    it("should estimate tokens for mixed English and Chinese", () => {
      const text = "Hello 你好 world 世界"; // 16 chars: 12 Latin + 4 CJK
      const tokens = estimateTokens(text);

      // Latin: 12/4 = 3, CJK: 4/1.5 = ~3, Total: ~6 tokens
      expect(tokens).toBeGreaterThanOrEqual(5);
      expect(tokens).toBeLessThanOrEqual(7);
    });

    it("should estimate tokens for Japanese text (Hiragana)", () => {
      const text = "こんにちは世界"; // 7 chars
      const tokens = estimateTokens(text);

      // ~7 / 1.5 = 5 tokens
      expect(tokens).toBeGreaterThanOrEqual(4);
      expect(tokens).toBeLessThanOrEqual(6);
    });

    it("should estimate tokens for Japanese text (Katakana)", () => {
      const text = "コンニチハセカイ"; // 8 chars
      const tokens = estimateTokens(text);

      // ~8 / 1.5 = 6 tokens
      expect(tokens).toBeGreaterThanOrEqual(5);
      expect(tokens).toBeLessThanOrEqual(7);
    });

    it("should estimate tokens for Korean text", () => {
      const text = "안녕하세요 세계"; // 8 chars (including space)
      const tokens = estimateTokens(text);

      // ~7 Hangul / 1.5 + 1 space/4 = ~5 tokens
      expect(tokens).toBeGreaterThanOrEqual(4);
      expect(tokens).toBeLessThanOrEqual(6);
    });

    it("should return 0 for empty text", () => {
      expect(estimateTokens("")).toBe(0);
      expect(estimateTokens("  ")).toBeGreaterThan(0); // Spaces count
    });
  });

  describe("estimateChatCost", () => {
    it("should calculate cost with context messages", () => {
      const contextMessages = [
        { role: "user", content: "Hello" },
        { role: "assistant", content: "Hi there!" },
      ];
      const inputMessage = "How are you?";

      const estimate = estimateChatCost(contextMessages, inputMessage);

      expect(estimate.contextTokens).toBeGreaterThan(0);
      expect(estimate.inputTokens).toBeGreaterThan(0);
      expect(estimate.totalTokens).toBeGreaterThan(estimate.contextTokens + estimate.inputTokens);
      expect(estimate.estimatedCredits).toBeGreaterThan(0);
    });

    it("should calculate cost for Chinese conversation", () => {
      const contextMessages = [
        { role: "user", content: "你好" },
        { role: "assistant", content: "你好！有什么可以帮助你的吗？" },
      ];
      const inputMessage = "请分析苹果公司的股票";

      const estimate = estimateChatCost(contextMessages, inputMessage);

      expect(estimate.contextTokens).toBeGreaterThan(0);
      expect(estimate.inputTokens).toBeGreaterThan(0);
      expect(estimate.estimatedCredits).toBeGreaterThan(0);
    });

    it("should handle empty context", () => {
      const estimate = estimateChatCost([], "Hello");

      expect(estimate.contextTokens).toBe(0);
      expect(estimate.inputTokens).toBeGreaterThan(0);
      expect(estimate.estimatedCredits).toBeGreaterThan(0);
    });
  });

  describe("Language-aware improvement comparison", () => {
    it("should estimate Chinese text more accurately than uniform approach", () => {
      const chineseText = "请分析一下这个股票的走势"; // 12 chars

      // Old approach: 12 / 4 = 3 tokens (too optimistic!)
      const oldEstimate = Math.ceil(chineseText.length / 4);

      // New approach: 12 / 1.5 = 8 tokens (more realistic)
      const newEstimate = estimateTokens(chineseText);

      expect(newEstimate).toBeGreaterThan(oldEstimate);
      expect(newEstimate).toBeGreaterThanOrEqual(7);
      expect(newEstimate).toBeLessThanOrEqual(9);
    });
  });
});
