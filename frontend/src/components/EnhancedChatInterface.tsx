import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { marketService, TimeInterval } from '../services/market';
import { useChatManager } from './chat/useChatManager';
import { useAnalysis } from './chat/useAnalysis';
import { ChatMessages } from './chat/ChatMessages';
import { ChatInput } from './chat/ChatInput';
import { ChartPanel } from './chat/ChartPanel';
import type { FibonacciAnalysisResponse } from '../services/analysis';

export function EnhancedChatInterface() {
    const [message, setMessage] = useState('');
    const [currentSymbol, setCurrentSymbol] = useState('');
    const [currentCompanyName, setCurrentCompanyName] = useState('');
    const [selectedInterval, setSelectedInterval] = useState<TimeInterval>('1d');
    const [selectedDateRange, setSelectedDateRange] = useState<{ start: string; end: string }>({ start: '', end: '' });

    const { messages, setMessages } = useChatManager();

    // Extract the latest Fibonacci analysis for the current symbol
    const currentFibonacciAnalysis = useMemo(() => {
        if (!currentSymbol) return null;

        // Find the most recent Fibonacci analysis message for the current symbol
        const fibMessage = [...messages]
            .reverse()
            .find(msg =>
                msg.role === 'assistant' &&
                msg.analysis_data &&
                msg.analysis_data.symbol === currentSymbol &&
                msg.analysis_data.fibonacci_levels
            );

        return fibMessage?.analysis_data as FibonacciAnalysisResponse | null;
    }, [messages, currentSymbol]);
    const analysisMutation = useAnalysis(currentSymbol, selectedDateRange, setMessages, setSelectedDateRange, selectedInterval);


    const getPeriodForInterval = (interval: string) => {
        switch (interval) {
            case '1h': return '1mo';
            case '1d': return '6mo';
            case '1wk': return '1y';
            case '1mo': return '2y';
            default: return '6mo';
        }
    };

    const priceDataQuery = useQuery({
        queryKey: ['priceData', currentSymbol, selectedInterval, selectedDateRange.start, selectedDateRange.end],
        queryFn: () => marketService.getPriceData(currentSymbol, {
            interval: selectedInterval,
            period: selectedDateRange.start && selectedDateRange.end ? undefined : getPeriodForInterval(selectedInterval),
            start_date: selectedDateRange.start || undefined,
            end_date: selectedDateRange.end || undefined,
        }),
        enabled: !!currentSymbol,
        staleTime: 30000,
        refetchInterval: 60000,
        retry: false
    });

    const handleSymbolSelect = (symbol: string, name: string) => {
        setCurrentSymbol(symbol);
        setCurrentCompanyName(name);
        setSelectedDateRange({ start: '', end: '' });
    };

    const handleIntervalChange = (interval: TimeInterval) => {
        setSelectedInterval(interval);
        setSelectedDateRange({ start: '', end: '' });
    };

    const handleDateRangeSelect = (startDate: string, endDate: string) => {
        setSelectedDateRange({ start: startDate, end: endDate });
    };

    const handleQuickAnalysis = (type: 'fibonacci' | 'fundamentals' | 'macro') => {
        if (type === 'macro') {
            analysisMutation.mutate('What is the current macro market sentiment?');
            return;
        }
        if (!currentSymbol) {
            setMessages(prev => [...prev, { role: 'assistant', content: '❌ **Error**: Please select a stock symbol first.', timestamp: new Date().toISOString() }]);
            return;
        }

        if (type === 'fibonacci') {
            // Create timeframe-specific message with current state values (not closure)
            const timeframeDisplay = selectedInterval === '1d' ? 'Daily' :
                                   selectedInterval === '1w' ? 'Weekly' :
                                   selectedInterval === '1M' ? 'Monthly' : selectedInterval;

            let queryWithTimeframe: string;

            if (selectedDateRange.start && selectedDateRange.end) {
                queryWithTimeframe = `Show me Fibonacci analysis for ${currentSymbol} (${timeframeDisplay} analysis: ${selectedDateRange.start} to ${selectedDateRange.end})`;
            } else {
                // Calculate the expected date range based on current interval
                const today = new Date();
                let periodsBack: Date;
                let periodDescription: string;

                switch (selectedInterval) {
                    case '1h':
                        periodsBack = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
                        periodDescription = "last 30 days";
                        break;
                    case '1d':
                        periodsBack = new Date(today.getTime() - 6 * 30 * 24 * 60 * 60 * 1000);
                        periodDescription = "last 6 months";
                        break;
                    case '1wk':
                        periodsBack = new Date(today.getTime() - 365 * 24 * 60 * 60 * 1000);
                        periodDescription = "last 1 year";
                        break;
                    case '1mo':
                        periodsBack = new Date(today.getTime() - 2 * 365 * 24 * 60 * 60 * 1000);
                        periodDescription = "last 2 years";
                        break;
                    default:
                        periodsBack = new Date(today.getTime() - 6 * 30 * 24 * 60 * 60 * 1000);
                        periodDescription = "last 6 months";
                }

                const autoStartDate = periodsBack.toISOString().split('T')[0];
                const autoEndDate = today.toISOString().split('T')[0];

                queryWithTimeframe = `Show me Fibonacci analysis for ${currentSymbol} (${timeframeDisplay} analysis for ${periodDescription}: ${autoStartDate} to ${autoEndDate})`;
            }

            analysisMutation.mutate(queryWithTimeframe);
            return;
        }

        const queries = {
            fundamentals: `Give me fundamental analysis for ${currentSymbol}`,
        };
        analysisMutation.mutate(queries[type]);
    };

    const handleSendMessage = () => {
        if (!message.trim()) return;
        analysisMutation.mutate(message);
        setMessage('');
    };

    return (
        <div className="bg-white rounded-lg shadow-sm border flex h-screen max-h-screen">
            <div className="flex flex-col w-1/2 border-r">
                <div className="border-b p-4 bg-gray-50">
                    <h3 className="text-lg font-medium text-gray-900">Financial Analysis Chat</h3>
                    <p className="text-sm text-gray-500">Ask questions and request analysis</p>
                </div>
                <ChatMessages messages={messages} isAnalysisPending={analysisMutation.isPending} />
                <ChatInput
                    message={message}
                    setMessage={setMessage}
                    onSendMessage={handleSendMessage}
                    isPending={analysisMutation.isPending}
                    currentSymbol={currentSymbol}
                />
            </div>
            <ChartPanel
                currentSymbol={currentSymbol}
                currentCompanyName={currentCompanyName}
                priceDataQuery={priceDataQuery}
                selectedInterval={selectedInterval}
                selectedDateRange={selectedDateRange}
                analysisMutation={analysisMutation}
                fibonacciAnalysis={currentFibonacciAnalysis}
                handleSymbolSelect={handleSymbolSelect}
                handleIntervalChange={handleIntervalChange}
                handleDateRangeSelect={handleDateRangeSelect}
                handleQuickAnalysis={handleQuickAnalysis}
            />
        </div>
    );
}