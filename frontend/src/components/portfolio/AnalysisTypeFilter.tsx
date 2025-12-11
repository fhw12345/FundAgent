/**
 * Analysis Type Filter Component for Portfolio Chat History.
 *
 * Allows filtering portfolio analysis history by analysis type:
 * - "individual" (Phase 1: individual symbol research)
 * - "portfolio" (Phase 2: portfolio-level trading decisions)
 */

import { useTranslation } from "react-i18next";

interface AnalysisTypeFilterProps {
  /** Currently selected analysis type (empty string for "All") */
  selectedType: string;
  /** Callback when analysis type selection changes */
  onTypeChange: (type: string) => void;
}

/**
 * Analysis type dropdown filter for portfolio analysis history.
 */
export function AnalysisTypeFilter({
  selectedType,
  onTypeChange,
}: AnalysisTypeFilterProps) {
  const { t } = useTranslation(['portfolio', 'common']);

  return (
    <div className="flex items-center gap-2">
      <select
        id="analysis-type-filter"
        value={selectedType}
        onChange={(e) => onTypeChange(e.target.value)}
        className="px-2 py-1 text-sm border border-gray-200 rounded-md bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
      >
        <option value="">{t('portfolio:filters.allTypes')}</option>
        <option value="individual">{t('portfolio:filters.individual')}</option>
        <option value="portfolio">{t('portfolio:filters.portfolio')}</option>
      </select>
    </div>
  );
}
