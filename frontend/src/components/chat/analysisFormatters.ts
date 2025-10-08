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
  // Get trend emoji
  const trendEmoji = result.market_structure.trend_direction
    .toLowerCase()
    .includes("up")
    ? "📈"
    : result.market_structure.trend_direction.toLowerCase().includes("down")
      ? "📉"
      : "➡️";

  // Build main trend table
  let mainTrendTable = "";
  if (result.raw_data?.top_trends && result.raw_data.top_trends.length > 0) {
    const mainTrend = result.raw_data.top_trends[0];
    const trendType = mainTrend.type.includes("Uptrend") ? "📈" : "📉";

    mainTrendTable = `
### ${trendType} Main Trend - ${mainTrend.type.toUpperCase()}

| Metric | Value |
|--------|-------|
| Period | ${mainTrend.period} |
| Magnitude | $${(mainTrend.magnitude || 0).toFixed(2)} move |
| Range | $${mainTrend.low?.toFixed(2)} → $${mainTrend.high?.toFixed(2)} |${result.pressure_zone ? `\n| Golden Zone | $${result.pressure_zone.lower_bound.toFixed(2)} - $${result.pressure_zone.upper_bound.toFixed(2)} |` : ""}

**Fibonacci Levels:**

| Level | Price |
|-------|-------|
${(mainTrend.fibonacci_levels || [])
  .map((level: any) => `| ${level.percentage} | $${level.price.toFixed(2)} |`)
  .join("\n")}
`;
  }

  return `## 📊 Fibonacci Analysis - ${result.symbol}

### ${trendEmoji} Bottom Line

| Metric | Value |
|--------|-------|
| Trend | ${result.market_structure.trend_direction.toUpperCase()} |
| Current Price | $${result.current_price.toFixed(2)} |
| Confidence | ${(result.confidence_score * 100).toFixed(1)}% |
| Period | ${result.start_date || "Dynamic"} to ${result.end_date || "Current"} |
${mainTrendTable}
`;
}

export function formatMacroResponse(result: MacroSentimentResponse): string {
  const sentimentEmoji =
    result.market_sentiment.toLowerCase() === "bullish"
      ? "📈"
      : result.market_sentiment.toLowerCase() === "bearish"
        ? "📉"
        : "➡️";

  const allSectors = Object.entries(result.sector_performance)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6);

  return `## 🌍 Macro Market Sentiment

### ${sentimentEmoji} Bottom Line

| Metric | Value |
|--------|-------|
| Market Sentiment | ${result.market_sentiment.toUpperCase()} |
| VIX Level | ${result.vix_level.toFixed(2)} (${result.vix_interpretation}) |
| Fear/Greed Score | ${result.fear_greed_score}/100 |

### 📝 Market Outlook

${result.market_outlook}

### 📊 Sector Performance

| Sector | Performance |
|--------|-------------|
${allSectors.map(([sector, perf]) => `| ${sector} | ${perf > 0 ? "+" : ""}${perf.toFixed(2)}% |`).join("\n")}

### 🔑 Key Factors
${result.key_factors.map((factor) => `• ${factor}`).join("\n")}
`;
}

export function formatFundamentalsResponse(
  result: StockFundamentalsResponse,
): string {
  const priceChangeEmoji = result.price_change >= 0 ? "📈" : "📉";
  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return `## 💼 Fundamentals - ${result.symbol}
*${result.company_name} • ${analysisDate}*

### ${priceChangeEmoji} Bottom Line

| Metric | Value |
|--------|-------|
| Current Price | $${result.current_price.toFixed(2)} (${result.price_change >= 0 ? "+" : ""}${result.price_change_percent.toFixed(2)}%) |
| Market Cap | $${(result.market_cap / 1e9).toFixed(2)}B |
${result.pe_ratio ? `| P/E Ratio | ${result.pe_ratio.toFixed(2)} |` : ""}
${result.pb_ratio ? `| P/B Ratio | ${result.pb_ratio.toFixed(2)} |` : ""}

### 📊 Valuation & Trading

| Metric | Value |
|--------|-------|
${result.dividend_yield ? `| Dividend Yield | ${result.dividend_yield.toFixed(2)}% |` : ""}
${result.beta ? `| Beta | ${result.beta.toFixed(2)} |` : ""}
| Volume | ${result.volume.toLocaleString()} |
| Avg Volume | ${result.avg_volume.toLocaleString()} |
| 52-Week High | $${result.fifty_two_week_high.toFixed(2)} |
| 52-Week Low | $${result.fifty_two_week_low.toFixed(2)} |
`;
}

export function formatStochasticResponse(
  result: StochasticAnalysisResponse,
): string {
  const signalEmoji =
    result.current_signal === "overbought"
      ? "🔴"
      : result.current_signal === "oversold"
        ? "🟢"
        : "🟡";

  const analysisDate = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  const recentSignals = result.signal_changes.slice(-3);

  return `## 📊 Stochastic Oscillator - ${result.symbol}
*${analysisDate} • ${result.timeframe} timeframe*

### ${signalEmoji} Bottom Line

| Indicator | Value |
|-----------|-------|
| Signal | ${result.current_signal.toUpperCase()} |
| Current Price | $${result.current_price.toFixed(2)} |
| %K Line | ${result.current_k.toFixed(1)}% |
| %D Line | ${result.current_d.toFixed(1)}% |
| Parameters | %K(${result.k_period}) %D(${result.d_period}) |

### 💡 Key Insights
${result.key_insights.map((insight) => `• ${insight}`).join("\n")}
${
  recentSignals.length > 0
    ? `
### 🔔 Recent Signals

${recentSignals.map((signal) => `• **${signal.type.toUpperCase()}**: ${signal.description}`).join("\n")}`
    : ""
}
`;
}
