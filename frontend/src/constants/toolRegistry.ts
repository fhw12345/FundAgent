/**
 * Tool Registry for UI Metadata
 *
 * Central registry mapping tool names to display metadata (title, icon).
 * Used by both button-triggered analysis and agent-invoked tools
 * for consistent UI rendering.
 */

import type { ToolCall } from "../types/api";

export const TOOL_REGISTRY = {
  fibonacci: { title: "Fibonacci Analysis", icon: "📊" },
  macro: { title: "Macro Sentiment", icon: "🌍" },
  company_overview: { title: "Company Overview", icon: "🏢" },
  stochastic: { title: "Stochastic Oscillator", icon: "📈" },
  cash_flow: { title: "Cash Flow", icon: "💵" },
  balance_sheet: { title: "Balance Sheet", icon: "📋" },
  news_sentiment: { title: "News Sentiment", icon: "📰" },
  market_movers: { title: "Market Movers", icon: "🔥" },
} as const;

export type ToolName = keyof typeof TOOL_REGISTRY;

/**
 * Helper to create ToolCall object with metadata from registry.
 *
 * @param toolName - Tool identifier (e.g., 'company_overview')
 * @param symbol - Stock symbol if applicable (e.g., 'TSLA')
 * @param metadata - Additional tool-specific data
 * @returns ToolCall object with title, icon, and metadata populated
 */
export function createToolCall(
  toolName: ToolName,
  symbol?: string,
  metadata?: Record<string, unknown>,
): ToolCall {
  const toolInfo = TOOL_REGISTRY[toolName] || {
    title: toolName,
    icon: "🔧",
  };

  return {
    tool_name: toolName,
    title: toolInfo.title,
    icon: toolInfo.icon,
    symbol,
    invoked_at: new Date().toISOString(),
    metadata,
  };
}
