/**
 * ExplanationPanel component with collapsible sections.
 * Provides rich, interactive explanation UI for metrics.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  BookOpen,
  Calculator,
  ChevronDown,
  Clock,
  Lightbulb,
} from "lucide-react";
import type { MetricExplanation } from "../../types/insights";

interface ExplanationPanelProps {
  explanation: MetricExplanation;
  dataSources: string[];
  defaultExpanded?: boolean;
}

interface CollapsibleSectionProps {
  title: string;
  icon: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
  variant?: "default" | "highlight";
}

/** Collapsible section with animation */
function CollapsibleSection({
  title,
  icon,
  defaultOpen = false,
  children,
  variant = "default",
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  const bgClass =
    variant === "highlight"
      ? "bg-gradient-to-r from-blue-50 to-indigo-50 border-blue-100"
      : "bg-gray-50/50 border-gray-100";

  return (
    <div className={`rounded-lg border ${bgClass} overflow-hidden`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-white/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="text-sm font-medium text-gray-700">{title}</span>
        </div>
        <div
          className={`transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
        >
          <ChevronDown className="w-4 h-4 text-gray-500" />
        </div>
      </button>
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isOpen ? "max-h-96 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-4 pb-4 pt-1">{children}</div>
      </div>
    </div>
  );
}

export function ExplanationPanel({
  explanation,
  dataSources,
  defaultExpanded = false,
}: ExplanationPanelProps) {
  const { t } = useTranslation(["insights"]);

  return (
    <div className="space-y-3">
      {/* Summary - always visible */}
      <div className="p-4 bg-white/80 rounded-lg border border-gray-100">
        <p className="text-sm text-gray-700 leading-relaxed">
          {explanation.detail}
        </p>
      </div>

      {/* Methodology section */}
      <CollapsibleSection
        title={t("insights:metric.methodology")}
        icon={<Calculator className="w-4 h-4 text-gray-500" />}
        defaultOpen={defaultExpanded}
      >
        <p className="text-sm text-gray-600 mb-3">{explanation.methodology}</p>
        {explanation.formula && (
          <div className="bg-white rounded-md p-3 border border-gray-200">
            <code className="text-xs font-mono text-gray-800 block whitespace-pre-wrap">
              {explanation.formula}
            </code>
          </div>
        )}
      </CollapsibleSection>

      {/* Historical context section */}
      <CollapsibleSection
        title={t("insights:metric.historical_context")}
        icon={<Clock className="w-4 h-4 text-gray-500" />}
        defaultOpen={defaultExpanded}
      >
        <p className="text-sm text-gray-600">{explanation.historical_context}</p>
      </CollapsibleSection>

      {/* Actionable insight - highlighted */}
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-4 border border-blue-100">
        <div className="flex items-start gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Lightbulb className="w-4 h-4 text-blue-600" />
          </div>
          <div>
            <h5 className="text-sm font-semibold text-blue-800 mb-1">
              {t("insights:metric.actionable_insight")}
            </h5>
            <p className="text-sm text-blue-700 leading-relaxed">
              {explanation.actionable_insight}
            </p>
          </div>
        </div>
      </div>

      {/* Data sources */}
      <CollapsibleSection
        title={t("insights:metric.data_sources")}
        icon={<BookOpen className="w-4 h-4 text-gray-500" />}
      >
        <div className="flex flex-wrap gap-2">
          {dataSources.map((source) => (
            <span
              key={source}
              className="text-xs bg-white text-gray-600 px-2.5 py-1 rounded-md border border-gray-200 font-mono"
            >
              {source}
            </span>
          ))}
        </div>
      </CollapsibleSection>
    </div>
  );
}

/** Compact explanation preview for collapsed state */
export function ExplanationPreview({
  summary,
}: {
  summary: string;
}) {
  return (
    <p className="text-sm text-gray-600 line-clamp-2">{summary}</p>
  );
}

export default ExplanationPanel;
