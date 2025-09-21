/**
 * useChart Hook
 *
 * This hook encapsulates the logic for initializing and managing the TradingView Lightweight Chart.
 * It handles chart creation, series management, data updates, event handling, and resizing.
 */

import { useEffect, useRef } from 'react'
import { createChart, IChartApi, ISeriesApi, MouseEventParams, CandlestickData, LineData } from 'lightweight-charts'

type ChartType = 'line' | 'candlestick'

export const useChart = (
    chartContainerRef: React.RefObject<HTMLDivElement>,
    chartType: ChartType,
    onDateRangeSelect?: (startDate: string, endDate: string) => void,
    setTooltip?: (tooltip: any) => void,
    interval?: string
) => {
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<'Line' | 'Candlestick'> | null>(null)

    useEffect(() => {
        if (!chartContainerRef.current) return

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { color: '#ffffff' },
                textColor: '#333',
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
            rightPriceScale: {
                borderColor: '#cccccc',
            },
            timeScale: {
                borderColor: '#cccccc',
                timeVisible: true,
                secondsVisible: false,
                fixLeftEdge: true,
                fixRightEdge: true,
            },
            grid: {
                vertLines: { color: '#f0f0f0' },
                horzLines: { color: '#f0f0f0' },
            },
            crosshair: {
                mode: 1,
                vertLine: { labelVisible: false },
                horzLine: { labelVisible: false },
            },
        })

        chartRef.current = chart

        if (chartType === 'line') {
            seriesRef.current = chart.addLineSeries({ color: '#2962FF', lineWidth: 2 })
        } else {
            seriesRef.current = chart.addCandlestickSeries({
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderVisible: false,
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350',
            })
        }

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth })
            }
        }
        window.addEventListener('resize', handleResize)

        return () => {
            window.removeEventListener('resize', handleResize)
            chart.remove()
        }
    }, [chartType, chartContainerRef])


    useEffect(() => {
        if (!chartRef.current || !seriesRef.current) return;

        let dateSelection = {
            startDate: null as string | null,
            endDate: null as string | null,
            clickCount: 0
        };

        const handleClick = (param: MouseEventParams) => {
            if (!param.time) return

            let date: Date;
            if (typeof param.time === 'number') {
                date = new Date(param.time * 1000)
            } else {
                date = new Date(param.time as string)
            }
            const timeStr = date.toISOString().split('T')[0]

            if (dateSelection.clickCount === 0) {
                dateSelection.startDate = timeStr;
                dateSelection.clickCount = 1;
            } else {
                const startDate = dateSelection.startDate!;
                const endDate = timeStr;

                const finalStartDate = startDate <= endDate ? startDate : endDate;
                const finalEndDate = startDate <= endDate ? endDate : startDate;

                onDateRangeSelect?.(finalStartDate, finalEndDate);
                dateSelection = { startDate: null, endDate: null, clickCount: 0 };
            }
        }

        const handleCrosshairMove = (param: MouseEventParams) => {
            if (!param.point || !param.time || !seriesRef.current || !setTooltip) {
                setTooltip({ visible: false })
                return
            }

            const data = param.seriesData.get(seriesRef.current)
            if (!data) {
                setTooltip({ visible: false })
                return
            }

            const price = 'value' in data ? data.value : data.close;
            const volume = 'volume' in data ? data.volume : undefined;
            const isGreen = 'close' in data && 'open' in data ? data.close >= data.open : undefined;

            let timeStr: string
            if (typeof param.time === 'number') {
                const date = new Date(param.time * 1000)
                timeStr = interval && (interval.includes('m') || interval.includes('h'))
                    ? `${date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}, ${date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}`
                    : date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
            } else {
                timeStr = new Date(param.time as string).toLocaleDateString('en-US', {
                    year: 'numeric',
                    month: 'short',
                    day: 'numeric'
                })
            }

            setTooltip({
                visible: true,
                x: param.point.x,
                y: param.point.y,
                time: timeStr,
                price: price,
                volume,
                isGreen
            })
        }

        chartRef.current.subscribeClick(handleClick)
        chartRef.current.subscribeCrosshairMove(handleCrosshairMove)

        return () => {
            if(chartRef.current) {
                chartRef.current.unsubscribeClick(handleClick);
                chartRef.current.unsubscribeCrosshairMove(handleCrosshairMove);
            }
        }
    }, [onDateRangeSelect, setTooltip, interval]);


    const setChartData = (data: (LineData | CandlestickData)[], highlightDateRange?: { start: string, end: string }) => {
        if (seriesRef.current) {
            seriesRef.current.setData(data);
            if (!highlightDateRange) {
                chartRef.current?.timeScale().fitContent();
            }
        }
    };

    return { chartRef, seriesRef, setChartData };
}