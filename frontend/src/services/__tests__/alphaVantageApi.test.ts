/**
 * Unit tests for Alpha Vantage API service
 *
 * Tests all Alpha Vantage endpoints including:
 * - getCompanyOverview (company fundamentals)
 * - getNewsSentiment (news with sentiment analysis)
 * - getCashFlow (annual/quarterly cash flow)
 * - getBalanceSheet (annual/quarterly balance sheet)
 * - getMarketMovers (top gainers/losers/most active)
 * - filterNewsSentiment (utility function for positive/negative filtering)
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { alphaVantageApi } from "../alphaVantageApi";
import { apiClient } from "../api";
import type { NewsSentimentResponse } from "../../types/alphaVantage";

// Mock the API client
vi.mock("../api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe("alphaVantageApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ===== getCompanyOverview Tests =====

  describe("getCompanyOverview", () => {
    it("should fetch company overview successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          Symbol: "AAPL",
          Name: "Apple Inc.",
          Description: "Technology company",
          Exchange: "NASDAQ",
          Currency: "USD",
          Country: "USA",
          Sector: "TECHNOLOGY",
          Industry: "Consumer Electronics",
          MarketCapitalization: "3000000000000",
          PERatio: "28.5",
          EPS: "6.5",
          Beta: "1.2",
          DividendYield: "0.005",
          "52WeekHigh": "200.0",
          "52WeekLow": "160.0",
          ProfitMargin: "0.25",
          RevenuePerShareTTM: "24.5",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getCompanyOverview("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/overview/AAPL");
      expect(result.Symbol).toBe("AAPL");
      expect(result.Name).toBe("Apple Inc.");
      expect(result.Sector).toBe("TECHNOLOGY");
    });

    it("should convert symbol to uppercase", async () => {
      // Arrange
      const mockResponse = {
        data: {
          Symbol: "TSLA",
          Name: "Tesla Inc.",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await alphaVantageApi.getCompanyOverview("tsla");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/overview/TSLA");
    });
  });

  // ===== getNewsSentiment Tests =====

  describe("getNewsSentiment", () => {
    it("should fetch news sentiment with default options", async () => {
      // Arrange
      const mockResponse = {
        data: {
          items: "50",
          sentiment_score_definition:
            "x <= -0.35: Bearish; -0.35 < x <= -0.15: Somewhat-Bearish; -0.15 < x < 0.15: Neutral; 0.15 <= x < 0.35: Somewhat_Bullish; x >= 0.35: Bullish",
          feed: [
            {
              title: "Apple hits record high",
              url: "https://example.com/1",
              time_published: "20250131T120000",
              authors: ["John Doe"],
              summary: "Apple stock rises",
              source: "CNBC",
              overall_sentiment_score: 0.8,
              overall_sentiment_label: "Bullish",
              ticker_sentiment: [
                {
                  ticker: "AAPL",
                  relevance_score: "0.9",
                  ticker_sentiment_score: "0.8",
                  ticker_sentiment_label: "Bullish",
                },
              ],
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getNewsSentiment("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/news-sentiment/AAPL?limit=50&sort=LATEST",
      );
      expect(result.feed).toHaveLength(1);
      expect(result.feed[0].overall_sentiment_label).toBe("Bullish");
    });

    it("should fetch news with custom limit and sort", async () => {
      // Arrange
      const mockResponse = {
        data: {
          items: "20",
          sentiment_score_definition: "...",
          feed: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await alphaVantageApi.getNewsSentiment("TSLA", {
        limit: 20,
        sort: "RELEVANCE",
      });

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/news-sentiment/TSLA?limit=20&sort=RELEVANCE",
      );
    });

    it("should convert symbol to uppercase", async () => {
      // Arrange
      const mockResponse = {
        data: {
          items: "50",
          sentiment_score_definition: "...",
          feed: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await alphaVantageApi.getNewsSentiment("msft");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/news-sentiment/MSFT?limit=50&sort=LATEST",
      );
    });

    it("should handle different sort options", async () => {
      // Arrange
      const mockResponse = {
        data: {
          items: "50",
          sentiment_score_definition: "...",
          feed: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      // Act & Assert - EARLIEST
      await alphaVantageApi.getNewsSentiment("AAPL", { sort: "EARLIEST" });
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/news-sentiment/AAPL?limit=50&sort=EARLIEST",
      );

      // Act & Assert - LATEST
      await alphaVantageApi.getNewsSentiment("AAPL", { sort: "LATEST" });
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/news-sentiment/AAPL?limit=50&sort=LATEST",
      );
    });
  });

  // ===== getCashFlow Tests =====

  describe("getCashFlow", () => {
    it("should fetch cash flow successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "AAPL",
          annualReports: [
            {
              fiscalDateEnding: "2024-09-30",
              operatingCashflow: "100000000000",
              capitalExpenditures: "10000000000",
              freeCashflow: "90000000000",
            },
          ],
          quarterlyReports: [
            {
              fiscalDateEnding: "2024-12-31",
              operatingCashflow: "25000000000",
              capitalExpenditures: "2500000000",
              freeCashflow: "22500000000",
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getCashFlow("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/cash-flow/AAPL");
      expect(result.symbol).toBe("AAPL");
      expect(result.annualReports).toHaveLength(1);
      expect(result.quarterlyReports).toHaveLength(1);
    });

    it("should convert symbol to uppercase", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "GOOGL",
          annualReports: [],
          quarterlyReports: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await alphaVantageApi.getCashFlow("googl");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/cash-flow/GOOGL");
    });
  });

  // ===== getBalanceSheet Tests =====

  describe("getBalanceSheet", () => {
    it("should fetch balance sheet successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "AAPL",
          annualReports: [
            {
              fiscalDateEnding: "2024-09-30",
              totalAssets: "350000000000",
              totalLiabilities: "250000000000",
              totalShareholderEquity: "100000000000",
              currentAssets: "150000000000",
              currentLiabilities: "100000000000",
            },
          ],
          quarterlyReports: [
            {
              fiscalDateEnding: "2024-12-31",
              totalAssets: "355000000000",
              totalLiabilities: "252000000000",
              totalShareholderEquity: "103000000000",
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getBalanceSheet("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/balance-sheet/AAPL",
      );
      expect(result.symbol).toBe("AAPL");
      expect(result.annualReports).toHaveLength(1);
      expect(result.quarterlyReports).toHaveLength(1);
    });

    it("should convert symbol to uppercase", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "MSFT",
          annualReports: [],
          quarterlyReports: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await alphaVantageApi.getBalanceSheet("msft");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/balance-sheet/MSFT",
      );
    });
  });

  // ===== getMarketMovers Tests =====

  describe("getMarketMovers", () => {
    it("should fetch market movers successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          metadata: "Top gainers, losers, and most actively traded US stocks",
          last_updated: "2025-01-31 16:00:00 US/Eastern",
          top_gainers: [
            {
              ticker: "NVDA",
              price: "500.00",
              change_amount: "25.00",
              change_percentage: "5.26%",
              volume: "100000000",
            },
          ],
          top_losers: [
            {
              ticker: "INTC",
              price: "40.00",
              change_amount: "-2.00",
              change_percentage: "-4.76%",
              volume: "80000000",
            },
          ],
          most_actively_traded: [
            {
              ticker: "AAPL",
              price: "183.50",
              change_amount: "1.50",
              change_percentage: "0.82%",
              volume: "150000000",
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getMarketMovers();

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/market-movers");
      expect(result.top_gainers).toHaveLength(1);
      expect(result.top_losers).toHaveLength(1);
      expect(result.most_actively_traded).toHaveLength(1);
      expect(result.last_updated).toBeDefined();
    });

    it("should handle empty market movers", async () => {
      // Arrange
      const mockResponse = {
        data: {
          metadata: "No data",
          last_updated: "2025-01-31 16:00:00 US/Eastern",
          top_gainers: [],
          top_losers: [],
          most_actively_traded: [],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await alphaVantageApi.getMarketMovers();

      // Assert
      expect(result.top_gainers).toHaveLength(0);
      expect(result.top_losers).toHaveLength(0);
      expect(result.most_actively_traded).toHaveLength(0);
    });
  });

  // ===== filterNewsSentiment Tests =====

  describe("filterNewsSentiment", () => {
    it("should filter top positive and negative news with defaults", () => {
      // Arrange
      const mockResponse: NewsSentimentResponse = {
        items: "10",
        sentiment_score_definition: "...",
        feed: [
          {
            title: "Very positive news",
            url: "https://example.com/1",
            time_published: "20250131T120000",
            authors: [],
            summary: "Great news",
            source: "CNBC",
            overall_sentiment_score: 0.9,
            overall_sentiment_label: "Bullish",
            ticker_sentiment: [],
          },
          {
            title: "Positive news",
            url: "https://example.com/2",
            time_published: "20250131T110000",
            authors: [],
            summary: "Good news",
            source: "Bloomberg",
            overall_sentiment_score: 0.5,
            overall_sentiment_label: "Somewhat-Bullish",
            ticker_sentiment: [],
          },
          {
            title: "Slightly positive",
            url: "https://example.com/3",
            time_published: "20250131T100000",
            authors: [],
            summary: "OK news",
            source: "Reuters",
            overall_sentiment_score: 0.2,
            overall_sentiment_label: "Somewhat-Bullish",
            ticker_sentiment: [],
          },
          {
            title: "Neutral news",
            url: "https://example.com/4",
            time_published: "20250131T090000",
            authors: [],
            summary: "Neutral",
            source: "WSJ",
            overall_sentiment_score: 0.05,
            overall_sentiment_label: "Neutral",
            ticker_sentiment: [],
          },
          {
            title: "Slightly negative",
            url: "https://example.com/5",
            time_published: "20250131T080000",
            authors: [],
            summary: "Not great",
            source: "MarketWatch",
            overall_sentiment_score: -0.2,
            overall_sentiment_label: "Somewhat-Bearish",
            ticker_sentiment: [],
          },
          {
            title: "Negative news",
            url: "https://example.com/6",
            time_published: "20250131T070000",
            authors: [],
            summary: "Bad news",
            source: "CNBC",
            overall_sentiment_score: -0.5,
            overall_sentiment_label: "Bearish",
            ticker_sentiment: [],
          },
          {
            title: "Very negative news",
            url: "https://example.com/7",
            time_published: "20250131T060000",
            authors: [],
            summary: "Terrible news",
            source: "Bloomberg",
            overall_sentiment_score: -0.9,
            overall_sentiment_label: "Bearish",
            ticker_sentiment: [],
          },
        ],
      };

      // Act
      const result = alphaVantageApi.filterNewsSentiment(mockResponse);

      // Assert
      expect(result.positive).toHaveLength(3); // Default maxPositive = 3
      expect(result.negative).toHaveLength(3); // Default maxNegative = 3
      expect(result.total).toBe(7);
      // Should be sorted by score descending for positive
      expect(result.positive[0].overall_sentiment_score).toBe(0.9);
      expect(result.positive[1].overall_sentiment_score).toBe(0.5);
      // Should be sorted by score ascending for negative (most negative first)
      expect(result.negative[0].overall_sentiment_score).toBe(-0.9);
      expect(result.negative[1].overall_sentiment_score).toBe(-0.5);
    });

    it("should filter with custom max positive and negative", () => {
      // Arrange
      const mockResponse: NewsSentimentResponse = {
        items: "5",
        sentiment_score_definition: "...",
        feed: [
          {
            title: "Positive 1",
            url: "https://example.com/1",
            time_published: "20250131T120000",
            authors: [],
            summary: "",
            source: "CNBC",
            overall_sentiment_score: 0.8,
            overall_sentiment_label: "Bullish",
            ticker_sentiment: [],
          },
          {
            title: "Positive 2",
            url: "https://example.com/2",
            time_published: "20250131T110000",
            authors: [],
            summary: "",
            source: "Bloomberg",
            overall_sentiment_score: 0.6,
            overall_sentiment_label: "Somewhat-Bullish",
            ticker_sentiment: [],
          },
          {
            title: "Negative 1",
            url: "https://example.com/3",
            time_published: "20250131T100000",
            authors: [],
            summary: "",
            source: "Reuters",
            overall_sentiment_score: -0.7,
            overall_sentiment_label: "Bearish",
            ticker_sentiment: [],
          },
          {
            title: "Negative 2",
            url: "https://example.com/4",
            time_published: "20250131T090000",
            authors: [],
            summary: "",
            source: "WSJ",
            overall_sentiment_score: -0.4,
            overall_sentiment_label: "Somewhat-Bearish",
            ticker_sentiment: [],
          },
        ],
      };

      // Act
      const result = alphaVantageApi.filterNewsSentiment(mockResponse, 1, 2);

      // Assert
      expect(result.positive).toHaveLength(1); // maxPositive = 1
      expect(result.negative).toHaveLength(2); // maxNegative = 2
      expect(result.total).toBe(4);
    });

    it("should exclude news with sentiment between -0.15 and 0.15", () => {
      // Arrange
      const mockResponse: NewsSentimentResponse = {
        items: "3",
        sentiment_score_definition: "...",
        feed: [
          {
            title: "Slightly positive (excluded)",
            url: "https://example.com/1",
            time_published: "20250131T120000",
            authors: [],
            summary: "",
            source: "CNBC",
            overall_sentiment_score: 0.1,
            overall_sentiment_label: "Neutral",
            ticker_sentiment: [],
          },
          {
            title: "Neutral (excluded)",
            url: "https://example.com/2",
            time_published: "20250131T110000",
            authors: [],
            summary: "",
            source: "Bloomberg",
            overall_sentiment_score: 0.0,
            overall_sentiment_label: "Neutral",
            ticker_sentiment: [],
          },
          {
            title: "Slightly negative (excluded)",
            url: "https://example.com/3",
            time_published: "20250131T100000",
            authors: [],
            summary: "",
            source: "Reuters",
            overall_sentiment_score: -0.1,
            overall_sentiment_label: "Neutral",
            ticker_sentiment: [],
          },
        ],
      };

      // Act
      const result = alphaVantageApi.filterNewsSentiment(mockResponse);

      // Assert
      expect(result.positive).toHaveLength(0); // All below 0.15 threshold
      expect(result.negative).toHaveLength(0); // All above -0.15 threshold
      expect(result.total).toBe(3);
    });

    it("should handle empty feed", () => {
      // Arrange
      const mockResponse: NewsSentimentResponse = {
        items: "0",
        sentiment_score_definition: "...",
        feed: [],
      };

      // Act
      const result = alphaVantageApi.filterNewsSentiment(mockResponse);

      // Assert
      expect(result.positive).toHaveLength(0);
      expect(result.negative).toHaveLength(0);
      expect(result.total).toBe(0);
    });
  });

  // ===== Integration Tests =====

  describe("Integration - Complete workflow", () => {
    it("should fetch news and filter sentiment", async () => {
      // Arrange
      const mockNewsResponse = {
        data: {
          items: "3",
          sentiment_score_definition: "...",
          feed: [
            {
              title: "Bullish news",
              url: "https://example.com/1",
              time_published: "20250131T120000",
              authors: [],
              summary: "Great",
              source: "CNBC",
              overall_sentiment_score: 0.8,
              overall_sentiment_label: "Bullish",
              ticker_sentiment: [],
            },
            {
              title: "Bearish news",
              url: "https://example.com/2",
              time_published: "20250131T110000",
              authors: [],
              summary: "Bad",
              source: "Bloomberg",
              overall_sentiment_score: -0.7,
              overall_sentiment_label: "Bearish",
              ticker_sentiment: [],
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockNewsResponse);

      // Act
      const newsData = await alphaVantageApi.getNewsSentiment("AAPL");
      const filtered = alphaVantageApi.filterNewsSentiment(newsData, 1, 1);

      // Assert
      expect(filtered.positive).toHaveLength(1);
      expect(filtered.negative).toHaveLength(1);
      expect(filtered.positive[0].overall_sentiment_label).toBe("Bullish");
      expect(filtered.negative[0].overall_sentiment_label).toBe("Bearish");
    });
  });
});
