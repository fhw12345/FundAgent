/**
 * useAnalysis Hook
 *
 * This hook manages the logic for making analysis requests to the backend.
 * It uses react-query's useMutation to handle the asynchronous nature of
 * API calls, including loading, success, and error states.
 */

import { useMutation } from '@tanstack/react-query'
import { analysisService } from '../../services/analysis'
import type { FibonacciAnalysisResponse, MacroSentimentResponse, StockFundamentalsResponse } from '../../services/analysis'

// Formatting functions
function formatFibonacciResponse(result: FibonacciAnalysisResponse): string {
    const keyLevels = result.fibonacci_levels.filter(level => level.is_key_level)

    return `## Fibonacci Analysis - ${result.symbol}

**Current Price:** $${result.current_price.toFixed(2)}
**Trend Direction:** ${result.market_structure.trend_direction}
**Confidence Score:** ${(result.confidence_score * 100).toFixed(1)}%

### Key Fibonacci Levels:
${keyLevels.map(level =>
    `• **${level.percentage}** - $${level.price.toFixed(2)}`
).join('\n')}

### Market Structure:
• **Swing High:** $${result.market_structure.swing_high.price.toFixed(2)} (${result.market_structure.swing_high.date})
• **Swing Low:** $${result.market_structure.swing_low.price.toFixed(2)} (${result.market_structure.swing_low.date})
• **Structure Quality:** ${result.market_structure.structure_quality}

### Analysis Summary:
${result.analysis_summary}

### Key Insights:
${result.key_insights.map(insight => `• ${insight}`).join('\n')}
`
}

function formatMacroResponse(result: MacroSentimentResponse): string {
    const topSectors = Object.entries(result.sector_performance)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)

    const bottomSectors = Object.entries(result.sector_performance)
        .sort(([, a], [, b]) => a - b)
        .slice(0, 3)

    return `## Macro Market Sentiment Analysis

**Overall Sentiment:** ${result.market_sentiment.toUpperCase()}
**VIX Level:** ${result.vix_level.toFixed(2)} (${result.vix_interpretation})
**Fear/Greed Score:** ${result.fear_greed_score}/100

### Top Performing Sectors:
${topSectors.map(([sector, perf]) => `• **${sector}**: ${perf > 0 ? '+' : ''}${perf.toFixed(2)}%`).join('\n')}

### Underperforming Sectors:
${bottomSectors.map(([sector, perf]) => `• **${sector}**: ${perf.toFixed(2)}%`).join('\n')}

### Market Outlook:
${result.market_outlook}

### Key Factors:
${result.key_factors.map(factor => `• ${factor}`).join('\n')}
`
}

function formatFundamentalsResponse(result: StockFundamentalsResponse): string {
    return `## Fundamental Analysis - ${result.symbol}

**Company:** ${result.company_name}
**Current Price:** $${result.current_price.toFixed(2)} (${result.price_change >= 0 ? '+' : ''}${result.price_change_percent.toFixed(2)}%)

### Valuation Metrics:
${result.pe_ratio ? `• **P/E Ratio:** ${result.pe_ratio.toFixed(2)}` : ''}
${result.pb_ratio ? `• **P/B Ratio:** ${result.pb_ratio.toFixed(2)}` : ''}
${result.dividend_yield ? `• **Dividend Yield:** ${result.dividend_yield.toFixed(2)}%` : ''}

### Financial Health:
• **Market Cap:** $${(result.market_cap / 1e9).toFixed(2)}B
• **Volume:** ${result.volume.toLocaleString()} (Avg: ${result.avg_volume.toLocaleString()})
${result.beta ? `• **Beta:** ${result.beta.toFixed(2)}` : ''}

### Price Range:
• **52-Week High:** $${result.fifty_two_week_high.toFixed(2)}
• **52-Week Low:** $${result.fifty_two_week_low.toFixed(2)}

### Summary:
${result.fundamental_summary}

### Key Metrics:
${result.key_metrics.map(metric => `• ${metric}`).join('\n')}
`
}


export const useAnalysis = (
    currentSymbol: string | null,
    selectedDateRange: { start: string; end: string },
    setMessages: (updater: (prevMessages: any[]) => any[]) => void,
    setSelectedDateRange: (range: { start: string; end: string }) => void
) => {
    return useMutation({
        mutationFn: async (userMessage: string) => {
            const intent = analysisService.parseAnalysisIntent(userMessage)
            const analysisSymbol = intent.symbol || currentSymbol

            switch (intent.type) {
                case 'fibonacci':
                    if (!analysisSymbol) throw new Error('Please select a stock symbol first.');
                    const startDate = selectedDateRange.start || intent.start_date;
                    const endDate = selectedDateRange.end || intent.end_date;

                    if (!startDate || !endDate) {
                        const today = new Date();
                        const sixMonthsAgo = new Date(today);
                        sixMonthsAgo.setMonth(today.getMonth() - 6);
                        const defaultStartDate = sixMonthsAgo.toISOString().split('T')[0];
                        const defaultEndDate = today.toISOString().split('T')[0];
                        setSelectedDateRange({ start: defaultStartDate, end: defaultEndDate });
                    }

                    const fibResult = await analysisService.fibonacciAnalysis({
                        symbol: analysisSymbol,
                        start_date: startDate || (new Date(Date.now() - 6 * 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]),
                        end_date: endDate || (new Date().toISOString().split('T')[0]),
                    });
                    return { type: 'fibonacci', content: formatFibonacciResponse(fibResult), analysis_data: fibResult };

                case 'macro':
                    const macroResult = await analysisService.macroSentimentAnalysis({});
                    return { type: 'macro', content: formatMacroResponse(macroResult), analysis_data: macroResult };

                case 'fundamentals':
                    if (!analysisSymbol) throw new Error('Please select a stock symbol first.');
                    const fundResult = await analysisService.stockFundamentals({ symbol: analysisSymbol });
                    return { type: 'fundamentals', content: formatFundamentalsResponse(fundResult), analysis_data: fundResult };

                default:
                    throw new Error("I can help with Fibonacci, Macro, and Fundamentals analysis.");
            }
        },
        onMutate: (newMessage) => {
            setMessages(prev => [...prev, { role: 'user', content: newMessage, timestamp: new Date().toISOString() }]);
        },
        onSuccess: (response) => {
            setMessages(prev => [...prev, { role: 'assistant', content: response.content, timestamp: new Date().toISOString(), analysis_data: response.analysis_data }]);
        },
        onError: (error: any) => {
            const errorContent = error?.response?.data?.detail || error.message || 'Unknown error';
            setMessages(prev => [...prev, { role: 'assistant', content: `❌ **Error**: ${errorContent}`, timestamp: new Date().toISOString() }]);
        },
    });
};