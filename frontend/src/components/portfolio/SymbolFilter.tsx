/**
 * Symbol Filter Component for Portfolio Chat History.
 *
 * Allows filtering portfolio analysis history by symbol.
 */

import { useTranslation } from "react-i18next";

interface SymbolFilterProps {
  /** Currently selected symbol (empty string for "All") */
  selectedSymbol: string;
  /** Callback when symbol selection changes */
  onSymbolChange: (symbol: string) => void;
  /** List of available symbols from chat history */
  availableSymbols: string[];
}

/**
 * Symbol dropdown filter for portfolio analysis history.
 */
export function SymbolFilter({
  selectedSymbol,
  onSymbolChange,
  availableSymbols,
}: SymbolFilterProps) {
  const { t } = useTranslation(['portfolio', 'common']);

  return (
    <div className="mb-4">
      <label
        htmlFor="symbol-filter"
        className="block text-sm font-medium text-gray-700 mb-2"
      >
        {t('portfolio:filters.symbol')}
      </label>
      <select
        id="symbol-filter"
        value={selectedSymbol}
        onChange={(e) => onSymbolChange(e.target.value)}
        className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 bg-white text-sm"
      >
        <option value="">{t('portfolio:filters.allSymbols')}</option>
        {availableSymbols.map((symbol) => (
          <option key={symbol} value={symbol}>
            {symbol}
          </option>
        ))}
      </select>
    </div>
  );
}
