/**
 * ChartTooltip Component
 *
 * Displays price, time, and volume information when hovering over the chart.
 */

import React from 'react'

interface TooltipData {
  visible: boolean
  x: number
  y: number
  time: string
  price: number
  volume?: number
  isGreen?: boolean
}

interface ChartTooltipProps {
  tooltipData: TooltipData
  chartContainerRef: React.RefObject<HTMLDivElement>
}

const formatPrice = (price: number) => {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)
}

const formatVolume = (volume: number) => {
  if (volume >= 1_000_000) {
    return `${(volume / 1_000_000).toFixed(1)}M`
  } else if (volume >= 1_000) {
    return `${(volume / 1_000).toFixed(1)}K`
  }
  return volume.toString()
}

export const ChartTooltip: React.FC<ChartTooltipProps> = ({ tooltipData, chartContainerRef }) => {
  if (!tooltipData.visible) {
    return null
  }

  return (
    <div
      className="absolute z-10 bg-black bg-opacity-90 text-white text-xs rounded px-2 py-1 pointer-events-none"
      style={{
        left: `${Math.min(tooltipData.x + 10, (chartContainerRef.current?.clientWidth || 0) - 150)}px`,
        top: `${Math.max(tooltipData.y - 10, 0)}px`,
      }}
    >
      <div>{tooltipData.time}</div>
      <div className={tooltipData.isGreen !== undefined ?
        (tooltipData.isGreen ? 'text-green-400' : 'text-red-400') : 'text-white'
      }>
        {formatPrice(tooltipData.price)}
      </div>
      {tooltipData.volume !== undefined && (
        <div className="text-gray-300">Vol: {formatVolume(tooltipData.volume)}</div>
      )}
    </div>
  )
}