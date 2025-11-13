/**
 * Alpha Vantage API TypeScript type definitions
 *
 * Corresponds to backend API responses from:
 * - /api/market/overview/{symbol}
 * - /api/market/news-sentiment/{symbol}
 * - /api/market/cash-flow/{symbol}
 * - /api/market/balance-sheet/{symbol}
 * - /api/market/market-movers
 */

// ========================================
// Company Overview Types
// ========================================

export interface CompanyOverview {
  Symbol: string;
  AssetType: string;
  Name: string;
  Description: string;
  CIK: string;
  Exchange: string;
  Currency: string;
  Country: string;
  Sector: string;
  Industry: string;
  Address: string;
  FiscalYearEnd: string;
  LatestQuarter: string;

  // Market Metrics
  MarketCapitalization: string; // numeric string
  EBITDA: string;
  PERatio: string;
  PEGRatio: string;
  BookValue: string;
  DividendPerShare: string;
  DividendYield: string;
  EPS: string;
  RevenuePerShareTTM: string;
  ProfitMargin: string;
  OperatingMarginTTM: string;
  ReturnOnAssetsTTM: string;
  ReturnOnEquityTTM: string;
  RevenueTTM: string;
  GrossProfitTTM: string;
  DilutedEPSTTM: string;
  QuarterlyEarningsGrowthYOY: string;
  QuarterlyRevenueGrowthYOY: string;
  AnalystTargetPrice: string;
  TrailingPE: string;
  ForwardPE: string;
  PriceToSalesRatioTTM: string;
  PriceToBookRatio: string;
  EVToRevenue: string;
  EVToEBITDA: string;
  Beta: string;

  // Price Metrics
  "52WeekHigh": string;
  "52WeekLow": string;
  "50DayMovingAverage": string;
  "200DayMovingAverage": string;

  // Share Metrics
  SharesOutstanding: string;
  DividendDate: string;
  ExDividendDate: string;
}

// ========================================
// News Sentiment Types
// ========================================

export interface NewsTickerSentiment {
  ticker: string;
  relevance_score: string; // "0.5" format
  ticker_sentiment_score: string; // "-0.1" format
  ticker_sentiment_label: string; // "Bearish" | "Bullish" | "Neutral"
}

export interface NewsFeedItem {
  title: string;
  url: string;
  time_published: string; // "20231115T120000"
  authors: string[];
  summary: string;
  banner_image?: string;
  source: string;
  category_within_source: string;
  source_domain: string;
  topics: Array<{
    topic: string;
    relevance_score: string;
  }>;
  overall_sentiment_score: number; // -1 to 1
  overall_sentiment_label: string; // "Bearish" | "Bullish" | "Neutral"
  ticker_sentiment: NewsTickerSentiment[];
}

export interface NewsSentimentResponse {
  items: string; // "50"
  sentiment_score_definition: string;
  relevance_score_definition: string;
  feed: NewsFeedItem[];
}

// ========================================
// Financial Statements Types
// ========================================

export interface CashFlowReport {
  fiscalDateEnding: string; // "2023-09-30"
  reportedCurrency: string;
  operatingCashflow: string;
  paymentsForOperatingActivities: string;
  proceedsFromOperatingActivities: string;
  changeInOperatingLiabilities: string;
  changeInOperatingAssets: string;
  depreciationDepletionAndAmortization: string;
  capitalExpenditures: string;
  changeInReceivables: string;
  changeInInventory: string;
  profitLoss: string;
  cashflowFromInvestment: string;
  cashflowFromFinancing: string;
  proceedsFromRepaymentsOfShortTermDebt: string;
  paymentsForRepurchaseOfCommonStock: string;
  paymentsForRepurchaseOfEquity: string;
  paymentsForRepurchaseOfPreferredStock: string;
  dividendPayout: string;
  dividendPayoutCommonStock: string;
  dividendPayoutPreferredStock: string;
  proceedsFromIssuanceOfCommonStock: string;
  proceedsFromIssuanceOfLongTermDebtAndCapitalSecuritiesNet: string;
  proceedsFromIssuanceOfPreferredStock: string;
  proceedsFromRepurchaseOfEquity: string;
  proceedsFromSaleOfTreasuryStock: string;
  changeInCashAndCashEquivalents: string;
  changeInExchangeRate: string;
  netIncome: string;
}

export interface CashFlowResponse {
  symbol: string;
  annualReports: CashFlowReport[];
  quarterlyReports: CashFlowReport[];
}

export interface BalanceSheetReport {
  fiscalDateEnding: string;
  reportedCurrency: string;
  totalAssets: string;
  totalCurrentAssets: string;
  cashAndCashEquivalentsAtCarryingValue: string;
  cashAndShortTermInvestments: string;
  inventory: string;
  currentNetReceivables: string;
  totalNonCurrentAssets: string;
  propertyPlantEquipment: string;
  accumulatedDepreciationAmortizationPPE: string;
  intangibleAssets: string;
  intangibleAssetsExcludingGoodwill: string;
  goodwill: string;
  investments: string;
  longTermInvestments: string;
  shortTermInvestments: string;
  otherCurrentAssets: string;
  otherNonCurrentAssets: string;
  totalLiabilities: string;
  totalCurrentLiabilities: string;
  currentAccountsPayable: string;
  deferredRevenue: string;
  currentDebt: string;
  shortTermDebt: string;
  totalNonCurrentLiabilities: string;
  capitalLeaseObligations: string;
  longTermDebt: string;
  currentLongTermDebt: string;
  longTermDebtNoncurrent: string;
  shortLongTermDebtTotal: string;
  otherCurrentLiabilities: string;
  otherNonCurrentLiabilities: string;
  totalShareholderEquity: string;
  treasuryStock: string;
  retainedEarnings: string;
  commonStock: string;
  commonStockSharesOutstanding: string;
}

export interface BalanceSheetResponse {
  symbol: string;
  annualReports: BalanceSheetReport[];
  quarterlyReports: BalanceSheetReport[];
}

// ========================================
// Market Movers Types
// ========================================

export interface MarketMover {
  ticker: string;
  price: string; // "150.25"
  change_amount: string; // "+5.75"
  change_percentage: string; // "+3.98%"
  volume: string; // "25000000"
}

export interface MarketMoversResponse {
  metadata: string;
  last_updated: string;
  top_gainers: MarketMover[];
  top_losers: MarketMover[];
  most_actively_traded: MarketMover[];
}

// ========================================
// Utility Types
// ========================================

/**
 * Parse numeric string to number with fallback
 */
export const parseNumericString = (
  value: string | undefined,
  fallback: number = 0,
): number => {
  if (!value || value === "None" || value === "N/A") return fallback;
  const parsed = parseFloat(value);
  return isNaN(parsed) ? fallback : parsed;
};

/**
 * Format large numbers (market cap, volume, etc.)
 */
export const formatLargeNumber = (value: number): string => {
  if (value >= 1e12) return `${(value / 1e12).toFixed(2)}T`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(2)}K`;
  return value.toFixed(2);
};

/**
 * Convert sentiment score (-1 to 1) to color class
 */
export const getSentimentColor = (score: number): string => {
  if (score > 0.15) return "text-green-600";
  if (score < -0.15) return "text-red-600";
  return "text-gray-600";
};

/**
 * Convert sentiment score to background color class
 */
export const getSentimentBgColor = (score: number): string => {
  if (score > 0.15) return "bg-green-50 border-green-200";
  if (score < -0.15) return "bg-red-50 border-red-200";
  return "bg-gray-50 border-gray-200";
};

/**
 * Format Alpha Vantage timestamp (YYYYMMDDTHHMMSS) to readable date
 */
export const formatAVTimestamp = (timestamp: string): string => {
  // "20231115T120000" → "Nov 15, 2023 12:00 PM"
  const year = timestamp.substring(0, 4);
  const month = timestamp.substring(4, 6);
  const day = timestamp.substring(6, 8);
  const hour = timestamp.substring(9, 11);
  const minute = timestamp.substring(11, 13);

  const date = new Date(`${year}-${month}-${day}T${hour}:${minute}:00`);
  return date.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
};
