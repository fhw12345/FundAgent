/**
 * Formatting functions for analysis responses.
 * Converts API responses into markdown for chat display.
 */

import type {
  FibonacciAnalysisResponse,
  MacroSentimentResponse,
  StockFundamentalsResponse,
  StochasticAnalysisResponse,
} from "../../services/analysis";

export function formatFibonacciResponse(
  result: FibonacciAnalysisResponse,
): string {
  const keyLevels = result.fibonacci_levels.filter(
    (level) => level.is_key_level,
  );

  // Format Big 3 trends with Fibonacci levels
  let bigThreeSection = "";
  if (result.raw_data?.top_trends && result.raw_data.top_trends.length > 0) {
    bigThreeSection = `
### 🎯 Big 3 Trends with Fibonacci Levels:

${result.raw_data.top_trends
  .slice(0, 3)
  .map((trend: any, index: number) => {
    const trendType = trend.type.includes("Uptrend") ? "📈" : "📉";
    const magnitude = (trend.magnitude || 0).toFixed(1);
    const isMainTrend = index === 0;

    const fibLevels = trend.fibonacci_levels || [];
    const keyFibLevels = fibLevels.filter((level: any) => level.is_key_level);

    let fibSection = "";
    if (keyFibLevels.length > 0) {
      fibSection = keyFibLevels
        .map(
          (level: any) =>
            `   • **${level.percentage}** - $${level.price.toFixed(2)}`,
        )
        .join("\n");
    } else if (fibLevels.length > 0) {
      fibSection = fibLevels
        .map(
          (level: any) =>
            `   • **${level.percentage}** - $${level.price.toFixed(2)}${level.is_key_level ? " 🌟" : ""}`,
        )
        .join("\n");
    } else {
      fibSection = "   • No levels calculated";
    }

    let pressureInfo = "";
    if (isMainTrend && result.pressure_zone) {
      pressureInfo = `\n   • **Golden Zone:** $${result.pressure_zone.lower_bound.toFixed(2)} - $${result.pressure_zone.upper_bound.toFixed(2)}`;
    }

    return `**${index + 1}. ${trendType} ${trend.type.toUpperCase()}** (${trend.period})
   • **Magnitude:** $${magnitude} move
   • **Range:** $${trend.low?.toFixed(2)} → $${trend.high?.toFixed(2)}
   • **Fibonacci Levels:**
${fibSection}${pressureInfo}`;
  })
  .join("\n\n")}
`;
  }

  return `## 📊 Fibonacci Analysis - ${result.symbol}

**Analysis Period:** ${result.start_date} to ${result.end_date} (${result.timeframe === "1h" ? "Hourly" : result.timeframe === "1d" ? "Daily" : result.timeframe === "1w" ? "Weekly" : result.timeframe === "1mo" ? "Monthly" : result.timeframe} timeframe)
**Current Price:** $${result.current_price.toFixed(2)}
**Trend Direction:** ${result.market_structure.trend_direction}
**Confidence Score:** ${(result.confidence_score * 100).toFixed(1)}%
${bigThreeSection}
`;
}

export function formatMacroResponse(result: MacroSentimentResponse): string {
  const topSectors = Object.entries(result.sector_performance)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 3);

  const bottomSectors = Object.entries(result.sector_performance)
    .sort(([, a], [, b]) => a - b)
    .slice(0, 3);

  return `## Macro Market Sentiment Analysis

**Overall Sentiment:** ${result.market_sentiment.toUpperCase()}
**VIX Level:** ${result.vix_level.toFixed(2)} (${result.vix_interpretation})
**Fear/Greed Score:** ${result.fear_greed_score}/100

### Top Performing Sectors:
${topSectors.map(([sector, perf]) => `• **${sector}**: ${perf > 0 ? "+" : ""}${perf.toFixed(2)}%`).join("\n")}

### Underperforming Sectors:
${bottomSectors.map(([sector, perf]) => `• **${sector}**: ${perf.toFixed(2)}%`).join("\n")}

### Market Outlook:
${result.market_outlook}

### Key Factors:
${result.key_factors.map((factor) => `• ${factor}`).join("\n")}
`;
}

export function formatFundamentalsResponse(
  result: StockFundamentalsResponse,
): string {
  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return `## Fundamental Analysis - ${result.symbol}
*Analysis Date: ${analysisDate}*

**Company:** ${result.company_name}
**Current Price:** $${result.current_price.toFixed(2)} (${result.price_change >= 0 ? "+" : ""}${result.price_change_percent.toFixed(2)}%)

### Valuation Metrics:
${result.pe_ratio ? `• **P/E Ratio:** ${result.pe_ratio.toFixed(2)}` : ""}
${result.pb_ratio ? `• **P/B Ratio:** ${result.pb_ratio.toFixed(2)}` : ""}
${result.dividend_yield ? `• **Dividend Yield:** ${result.dividend_yield.toFixed(2)}%` : ""}

### Financial Health:
• **Market Cap:** $${(result.market_cap / 1e9).toFixed(2)}B
• **Volume:** ${result.volume.toLocaleString()} (Avg: ${result.avg_volume.toLocaleString()})
${result.beta ? `• **Beta:** ${result.beta.toFixed(2)} (volatility vs market)` : ""}

### Price Range:
• **52-Week High:** $${result.fifty_two_week_high.toFixed(2)}
• **52-Week Low:** $${result.fifty_two_week_low.toFixed(2)}
`;
}

export function formatStochasticResponse(
  result: StochasticAnalysisResponse,
): string {
  const signalEmoji =
    result.current_signal === "overbought"
      ? "📈"
      : result.current_signal === "oversold"
        ? "📉"
        : "➡️";

  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const recentSignals = result.signal_changes.slice(-3);

  return `## ${signalEmoji} Stochastic Oscillator Analysis - ${result.symbol}
*Analysis Date: ${analysisDate}*

**Analysis Period:** ${result.start_date || "Dynamic"} to ${result.end_date || "Current"} (${result.timeframe} timeframe)
**Current Price:** $${result.current_price.toFixed(2)}
**Parameters:** %K(${result.k_period}) %D(${result.d_period})

### Current Readings:
• **%K Line:** ${result.current_k.toFixed(2)}%
• **%D Line:** ${result.current_d.toFixed(2)}%
• **Signal:** ${result.current_signal.toUpperCase()} ${signalEmoji}

${
  recentSignals.length > 0
    ? `### Recent Signals:
${recentSignals.map((signal) => `• **${signal.type.toUpperCase()}**: ${signal.description}`).join("\n")}
`
    : ""
}

### Analysis Summary:
${result.analysis_summary}

### Key Insights:
${result.key_insights.map((insight) => `• ${insight}`).join("\n")}
`;
}
