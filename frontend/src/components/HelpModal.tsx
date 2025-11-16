import type { KeyboardEvent } from 'react'
import { X, Bot, MessageSquare, TrendingUp, ArrowRight, ChevronDown } from 'lucide-react'

interface HelpModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function HelpModal({ isOpen, onClose }: HelpModalProps) {
  if (!isOpen) return null

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose()
    }
  }

  return (
    /* eslint-disable jsx-a11y/no-noninteractive-element-interactions */
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="help-modal-title"
      tabIndex={-1}
      className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={onClose}
      onKeyDown={handleKeyDown}
    >
      {/* eslint-disable jsx-a11y/no-static-element-interactions */}
      <div
        className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        {/* eslint-enable jsx-a11y/no-static-element-interactions */}
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-500 to-indigo-500 text-white p-6 rounded-t-2xl flex justify-between items-center">
          <h2 id="help-modal-title" className="text-2xl font-bold">How to Use Financial Agent</h2>
          <button
            onClick={onClose}
            className="text-white hover:bg-white/20 rounded-lg p-2 transition-colors"
            aria-label="Close modal"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Agent Mode Section */}
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-xl p-6 border-l-4 border-blue-500 shadow-lg">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-blue-500 text-white p-3 rounded-lg">
                <Bot className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-blue-900">🤖 Agent Mode</h3>
                <p className="text-sm text-blue-700">Intelligent automated analysis</p>
              </div>
            </div>

            <p className="text-gray-700 mb-4">
              The agent autonomously analyzes your query, automatically selects the right tools,
              and provides comprehensive insights with actionable suggestions.
            </p>

            {/* Flow Diagram */}
            <div className="bg-white/60 backdrop-blur-sm rounded-lg p-4 border border-blue-200">
              <div className="flex items-center justify-between text-sm">
                <div className="flex-1 text-center">
                  <div className="bg-blue-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    1. Ask Question
                  </div>
                  <p className="text-xs text-gray-600">Type your query</p>
                </div>
                <ArrowRight className="w-5 h-5 text-blue-500 mx-2 flex-shrink-0" />
                <div className="flex-1 text-center">
                  <div className="bg-blue-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    2. Agent Analyzes
                  </div>
                  <p className="text-xs text-gray-600">AI processes</p>
                </div>
                <ArrowRight className="w-5 h-5 text-blue-500 mx-2 flex-shrink-0" />
                <div className="flex-1 text-center">
                  <div className="bg-blue-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    3. Auto-select Tools
                  </div>
                  <p className="text-xs text-gray-600">Market data, news, etc.</p>
                </div>
                <ArrowRight className="w-5 h-5 text-blue-500 mx-2 flex-shrink-0" />
                <div className="flex-1 text-center">
                  <div className="bg-blue-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    4. Get Insights
                  </div>
                  <p className="text-xs text-gray-600">Suggestions & summary</p>
                </div>
              </div>
            </div>
          </div>

          {/* Copilot Mode Section */}
          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-xl p-6 border-l-4 border-purple-500 shadow-lg">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-purple-500 text-white p-3 rounded-lg">
                <MessageSquare className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-purple-900">💬 Copilot Mode</h3>
                <p className="text-sm text-purple-700">Manual exploration with AI guidance</p>
              </div>
            </div>

            <p className="text-gray-700 mb-4">
              You control the analysis by clicking buttons to trigger specific analyses and view charts.
              The AI helps you understand the results and provides context.
            </p>

            {/* Flow Diagram */}
            <div className="bg-white/60 backdrop-blur-sm rounded-lg p-4 border border-purple-200">
              <div className="flex items-center justify-between text-sm">
                <div className="flex-1 text-center">
                  <div className="bg-purple-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    1. Click Analysis
                  </div>
                  <p className="text-xs text-gray-600">Choose tool button</p>
                </div>
                <ArrowRight className="w-5 h-5 text-purple-500 mx-2 flex-shrink-0" />
                <div className="flex-1 text-center">
                  <div className="bg-purple-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    2. View Chart
                  </div>
                  <p className="text-xs text-gray-600">Visual data display</p>
                </div>
                <ArrowRight className="w-5 h-5 text-purple-500 mx-2 flex-shrink-0" />
                <div className="flex-1 text-center">
                  <div className="bg-purple-500 text-white rounded-lg py-2 px-3 mb-1 font-medium">
                    3. AI Explains
                  </div>
                  <p className="text-xs text-gray-600">Context & insights</p>
                </div>
              </div>
            </div>
          </div>

          {/* Portfolio Agent Section */}
          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-xl p-6 border-l-4 border-green-500 shadow-lg">
            <div className="flex items-center gap-3 mb-4">
              <div className="bg-green-500 text-white p-3 rounded-lg">
                <TrendingUp className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-green-900">📊 Portfolio Agent</h3>
                <p className="text-sm text-green-700">Track simulated trading performance</p>
              </div>
            </div>

            <p className="text-gray-700 mb-4">
              Navigate to the Portfolio page to view your simulated holdings, transaction history,
              and profit/loss performance. The agent mimics real trading scenarios.
            </p>

            {/* Flow Diagram */}
            <div className="bg-white/60 backdrop-blur-sm rounded-lg p-4 border border-green-200">
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center flex-shrink-0 font-bold">
                    1
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-800">Go to Portfolio Tab</p>
                    <p className="text-xs text-gray-600">Click &ldquo;Portfolio&rdquo; in the top navigation</p>
                  </div>
                </div>
                <ChevronDown className="w-5 h-5 text-green-500 mx-auto" />
                <div className="flex items-start gap-3">
                  <div className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center flex-shrink-0 font-bold">
                    2
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-800">View Holdings Dashboard</p>
                    <p className="text-xs text-gray-600">See current positions and allocations</p>
                  </div>
                </div>
                <ChevronDown className="w-5 h-5 text-green-500 mx-auto" />
                <div className="flex items-start gap-3">
                  <div className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center flex-shrink-0 font-bold">
                    3
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-800">Check Transaction History</p>
                    <p className="text-xs text-gray-600">Review buy/sell transactions</p>
                  </div>
                </div>
                <ChevronDown className="w-5 h-5 text-green-500 mx-auto" />
                <div className="flex items-start gap-3">
                  <div className="bg-green-500 text-white rounded-full w-8 h-8 flex items-center justify-center flex-shrink-0 font-bold">
                    4
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-800">Analyze P&L Performance</p>
                    <p className="text-xs text-gray-600">Track earnings and losses over time</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-gray-50 p-4 rounded-b-2xl text-center">
          <p className="text-sm text-gray-600">
            Need more help? Contact support or check our documentation
          </p>
        </div>
      </div>
      {/* eslint-enable jsx-a11y/no-noninteractive-element-interactions */}
    </div>
  )
}
