/**
 * Quick Analysis Panel - Button-based analysis triggers
 */

import {
  BarChart3,
  TrendingUp,
  DollarSign,
  LineChart,
  Activity,
} from "lucide-react";

interface QuickAnalysisPanelProps {
  currentSymbol: string;
  onAnalysisClick: (
    actionType: "fibonacci" | "fundamentals" | "chart" | "macro" | "stochastic",
  ) => void;
  disabled: boolean;
}

export function QuickAnalysisPanel({
  currentSymbol,
  onAnalysisClick,
  disabled,
}: QuickAnalysisPanelProps) {
  const hasSymbol = currentSymbol.trim().length > 0;

  return (
    <div className="mb-3">
      <p className="text-xs text-gray-500 mb-2">Quick Analysis:</p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => onAnalysisClick("fibonacci")}
          disabled={disabled}
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
            hasSymbol
              ? "bg-blue-100 text-blue-800 hover:bg-blue-200"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          <BarChart3 className="h-3 w-3 mr-1" />
          Fibonacci
        </button>
        <button
          onClick={() => onAnalysisClick("macro")}
          disabled={disabled}
          className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 hover:bg-green-200 disabled:opacity-50"
        >
          <TrendingUp className="h-3 w-3 mr-1" />
          Macro
        </button>
        <button
          onClick={() => onAnalysisClick("fundamentals")}
          disabled={disabled}
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
            hasSymbol
              ? "bg-purple-100 text-purple-800 hover:bg-purple-200"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          <DollarSign className="h-3 w-3 mr-1" />
          Fundamentals
        </button>
        <button
          onClick={() => onAnalysisClick("chart")}
          disabled={disabled}
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
            hasSymbol
              ? "bg-orange-100 text-orange-800 hover:bg-orange-200"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          <LineChart className="h-3 w-3 mr-1" />
          Chart
        </button>
        <button
          onClick={() => onAnalysisClick("stochastic")}
          disabled={disabled}
          className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium disabled:opacity-50 ${
            hasSymbol
              ? "bg-indigo-100 text-indigo-800 hover:bg-indigo-200"
              : "bg-gray-100 text-gray-500 hover:bg-gray-200"
          }`}
        >
          <Activity className="h-3 w-3 mr-1" />
          Stochastic
        </button>
      </div>
    </div>
  );
}
