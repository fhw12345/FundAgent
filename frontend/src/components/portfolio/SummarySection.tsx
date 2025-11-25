/**
 * Summary Section Component for Portfolio Chat History.
 *
 * Displays a collapsible summary of compacted chat history.
 * Shows when historical context has been summarized to save tokens.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";

interface SummarySectionProps {
  /** Summary text (markdown formatted) */
  summaryText: string;
  /** Original message count before compaction */
  originalCount: number;
  /** Compacted message count after summarization */
  compactedCount: number;
  /** Compression ratio (e.g., 0.1 for 10%) */
  compressionRatio: number;
}

/**
 * Collapsible summary section showing compacted chat history.
 *
 * Option C implementation: Summary shown in collapsible section,
 * allows users to see what context was compressed.
 */
export function SummarySection({
  summaryText,
  originalCount,
  compactedCount,
  compressionRatio,
}: SummarySectionProps) {
  const { t } = useTranslation(['portfolio', 'common']);
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="mb-4 border border-blue-200 rounded-md bg-blue-50">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between text-left hover:bg-blue-100 transition-colors rounded-t-md"
      >
        <div className="flex items-center space-x-2">
          {isExpanded ? (
            <ChevronDownIcon className="h-4 w-4 text-blue-600" />
          ) : (
            <ChevronRightIcon className="h-4 w-4 text-blue-600" />
          )}
          <span className="text-sm font-medium text-blue-900">
            {t('portfolio:summary.title')}
          </span>
          <span className="text-xs text-blue-700 bg-blue-100 px-2 py-0.5 rounded-full">
            {t('portfolio:summary.compressed', {
              from: originalCount,
              to: compactedCount,
              percent: Math.round(compressionRatio * 100),
            })}
          </span>
        </div>
      </button>

      {/* Expanded Content */}
      {isExpanded && (
        <div className="px-3 py-2 border-t border-blue-200">
          <div className="text-xs text-blue-800 mb-2">
            {t('portfolio:summary.description')}
          </div>
          <div className="prose prose-sm max-w-none text-gray-700 bg-white p-3 rounded border border-blue-100">
            {/* Render summary as plain text or markdown */}
            <div className="whitespace-pre-wrap">{summaryText}</div>
          </div>
          <div className="text-xs text-blue-600 mt-2 italic">
            {t('portfolio:summary.hint')}
          </div>
        </div>
      )}
    </div>
  );
}
