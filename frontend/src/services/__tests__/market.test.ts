/**
 * Unit tests for market data service
 *
 * Tests symbol search, price data, quote fetching, formatting, and utility functions including:
 * - searchSymbols with API calls
 * - getPriceData with interval/period options and error handling
 * - getSymbolInfo and getQuote
 * - convertToChartData (line and candlestick)
 * - getRecommendedInterval based on period
 * - formatPrice and formatVolume
 * - calculatePriceChange with positive/negative scenarios
 * - createDebouncedSearch with delay and query length checks
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { marketService, type PriceDataPoint } from "../market";
import { apiClient } from "../api";

// Mock the API client
vi.mock("../api", () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

describe("marketService", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ===== searchSymbols Tests =====

  describe("searchSymbols", () => {
    it("should search symbols successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          query: "AAPL",
          results: [
            {
              symbol: "AAPL",
              name: "Apple Inc.",
              exchange: "NASDAQ",
              type: "Common Stock",
              match_type: "exact",
              confidence: 1.0,
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await marketService.searchSymbols("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/search?q=AAPL",
      );
      expect(result.query).toBe("AAPL");
      expect(result.results).toHaveLength(1);
      expect(result.results[0].symbol).toBe("AAPL");
    });

    it("should encode special characters in query", async () => {
      // Arrange
      const mockResponse = {
        data: { query: "A&B", results: [] },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await marketService.searchSymbols("A&B");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/search?q=A%26B",
      );
    });

    it("should return empty results for no matches", async () => {
      // Arrange
      const mockResponse = {
        data: { query: "INVALID", results: [] },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await marketService.searchSymbols("INVALID");

      // Assert
      expect(result.results).toHaveLength(0);
    });
  });

  // ===== getPriceData Tests =====

  describe("getPriceData", () => {
    it("should get price data with default interval", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "AAPL",
          interval: "1d",
          data: [
            {
              time: "2025-01-31",
              open: 180.0,
              high: 185.0,
              low: 179.0,
              close: 183.0,
              volume: 50000000,
            },
          ],
          last_updated: "2025-01-31T20:00:00Z",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await marketService.getPriceData("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/price/AAPL?interval=1d",
      );
      expect(result.symbol).toBe("AAPL");
      expect(result.data).toHaveLength(1);
    });

    it("should get price data with custom interval and period", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "TSLA",
          interval: "5m",
          data: [],
          last_updated: "2025-01-31T20:00:00Z",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await marketService.getPriceData("TSLA", {
        interval: "5m",
        period: "1d",
      });

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/price/TSLA?interval=5m&period=1d",
      );
    });

    it("should get price data with start_date and end_date", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "MSFT",
          interval: "1d",
          data: [],
          last_updated: "2025-01-31T20:00:00Z",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      await marketService.getPriceData("MSFT", {
        start_date: "2025-01-01",
        end_date: "2025-01-31",
      });

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith(
        "/api/market/price/MSFT?interval=1d&start_date=2025-01-01&end_date=2025-01-31",
      );
    });

    it("should handle error with object detail", async () => {
      // Arrange
      const mockError = {
        response: {
          data: {
            detail: {
              message: "Symbol not found",
              suggestions: ["AAPL", "GOOGL"],
            },
          },
        },
      };
      vi.mocked(apiClient.get).mockRejectedValueOnce(mockError);

      // Act & Assert
      try {
        await marketService.getPriceData("INVALID");
        expect.fail("Should have thrown an error");
      } catch (err: any) {
        expect(err.message).toBe("Symbol not found");
        expect(err.suggestions).toEqual(["AAPL", "GOOGL"]);
        expect(err.original).toBe(mockError);
      }
    });

    it("should handle error with string detail", async () => {
      // Arrange
      const mockError = {
        response: {
          data: {
            detail: "Rate limit exceeded",
          },
        },
      };
      vi.mocked(apiClient.get).mockRejectedValueOnce(mockError);

      // Act & Assert
      try {
        await marketService.getPriceData("AAPL");
        expect.fail("Should have thrown an error");
      } catch (err: any) {
        expect(err.message).toBe("Rate limit exceeded");
        expect(err.suggestions).toEqual([]);
      }
    });

    it("should rethrow error if no detail provided", async () => {
      // Arrange
      const mockError = new Error("Network error");
      vi.mocked(apiClient.get).mockRejectedValueOnce(mockError);

      // Act & Assert
      await expect(marketService.getPriceData("AAPL")).rejects.toThrow(
        "Network error",
      );
    });
  });

  // ===== getSymbolInfo Tests =====

  describe("getSymbolInfo", () => {
    it("should get symbol info successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "AAPL",
          name: "Apple Inc.",
          sector: "Technology",
          industry: "Consumer Electronics",
          exchange: "NASDAQ",
          currency: "USD",
          market_cap: 3000000000000,
          current_price: 183.5,
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await marketService.getSymbolInfo("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/info/AAPL");
      expect(result.symbol).toBe("AAPL");
      expect(result.name).toBe("Apple Inc.");
      expect(result.sector).toBe("Technology");
    });
  });

  // ===== getQuote Tests =====

  describe("getQuote", () => {
    it("should get real-time quote successfully", async () => {
      // Arrange
      const mockResponse = {
        data: {
          symbol: "AAPL",
          price: 183.5,
          open: 180.0,
          high: 185.0,
          low: 179.5,
          volume: 50000000,
          latest_trading_day: "2025-01-31",
          previous_close: 180.0,
          change: 3.5,
          change_percent: "+1.94%",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

      // Act
      const result = await marketService.getQuote("AAPL");

      // Assert
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/quote/AAPL");
      expect(result.symbol).toBe("AAPL");
      expect(result.price).toBe(183.5);
      expect(result.change).toBe(3.5);
    });
  });

  // ===== convertToChartData Tests =====

  describe("convertToChartData", () => {
    const mockPriceData: PriceDataPoint[] = [
      {
        time: "2025-01-29",
        open: 180.0,
        high: 185.0,
        low: 179.0,
        close: 183.0,
        volume: 50000000,
      },
      {
        time: "2025-01-30",
        open: 183.0,
        high: 187.0,
        low: 182.0,
        close: 186.0,
        volume: 52000000,
      },
    ];

    it("should convert to line chart data", () => {
      // Act
      const result = marketService.convertToChartData(mockPriceData, "line");

      // Assert
      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({ time: "2025-01-29", value: 183.0 });
      expect(result[1]).toEqual({ time: "2025-01-30", value: 186.0 });
    });

    it("should convert to line chart data by default", () => {
      // Act
      const result = marketService.convertToChartData(mockPriceData);

      // Assert
      expect(result[0]).toHaveProperty("value");
      expect(result[0]).not.toHaveProperty("open");
    });

    it("should convert to candlestick chart data", () => {
      // Act
      const result = marketService.convertToChartData(
        mockPriceData,
        "candlestick",
      );

      // Assert
      expect(result).toHaveLength(2);
      expect(result[0]).toEqual({
        time: "2025-01-29",
        open: 180.0,
        high: 185.0,
        low: 179.0,
        close: 183.0,
      });
      expect(result[0]).not.toHaveProperty("volume");
    });

    it("should handle empty price data array", () => {
      // Act
      const result = marketService.convertToChartData([]);

      // Assert
      expect(result).toEqual([]);
    });
  });

  // ===== getRecommendedInterval Tests =====

  describe("getRecommendedInterval", () => {
    it("should recommend 5m for 1d period", () => {
      expect(marketService.getRecommendedInterval("1d")).toBe("5m");
    });

    it("should recommend 15m for 5d period", () => {
      expect(marketService.getRecommendedInterval("5d")).toBe("15m");
    });

    it("should recommend 60m for 1mo period", () => {
      expect(marketService.getRecommendedInterval("1mo")).toBe("60m");
    });

    it("should recommend 1d for 3mo, 6mo, 1y, ytd periods", () => {
      expect(marketService.getRecommendedInterval("3mo")).toBe("1d");
      expect(marketService.getRecommendedInterval("6mo")).toBe("1d");
      expect(marketService.getRecommendedInterval("1y")).toBe("1d");
      expect(marketService.getRecommendedInterval("ytd")).toBe("1d");
    });

    it("should recommend 1w for 2y and 5y periods", () => {
      expect(marketService.getRecommendedInterval("2y")).toBe("1w");
      expect(marketService.getRecommendedInterval("5y")).toBe("1w");
    });

    it("should recommend 1mo for max period", () => {
      expect(marketService.getRecommendedInterval("max")).toBe("1mo");
    });
  });

  // ===== formatPrice Tests =====

  describe("formatPrice", () => {
    it("should format USD price with 2 decimals", () => {
      const result = marketService.formatPrice(183.5);
      expect(result).toBe("$183.50");
    });

    it("should format large USD price", () => {
      const result = marketService.formatPrice(1234567.89);
      expect(result).toBe("$1,234,567.89");
    });

    it("should format zero price", () => {
      const result = marketService.formatPrice(0);
      expect(result).toBe("$0.00");
    });

    it("should format custom currency", () => {
      const result = marketService.formatPrice(100, "EUR");
      expect(result).toContain("100.00");
    });
  });

  // ===== formatVolume Tests =====

  describe("formatVolume", () => {
    it("should format billions with 'B' suffix", () => {
      expect(marketService.formatVolume(5_000_000_000)).toBe("5.0B");
      expect(marketService.formatVolume(12_345_000_000)).toBe("12.3B");
    });

    it("should format millions with 'M' suffix", () => {
      expect(marketService.formatVolume(50_000_000)).toBe("50.0M");
      expect(marketService.formatVolume(123_456_789)).toBe("123.5M");
    });

    it("should format thousands with 'K' suffix", () => {
      expect(marketService.formatVolume(5_000)).toBe("5.0K");
      expect(marketService.formatVolume(123_456)).toBe("123.5K");
    });

    it("should format small volumes without suffix", () => {
      expect(marketService.formatVolume(999)).toBe("999");
      expect(marketService.formatVolume(500)).toBe("500");
    });

    it("should handle zero volume", () => {
      expect(marketService.formatVolume(0)).toBe("0");
    });
  });

  // ===== calculatePriceChange Tests =====

  describe("calculatePriceChange", () => {
    it("should calculate positive price change", () => {
      // Act
      const result = marketService.calculatePriceChange(183.5, 180.0);

      // Assert
      expect(result.change).toBe(3.5);
      expect(result.changePercent).toBeCloseTo(1.94, 1);
      expect(result.isPositive).toBe(true);
      expect(result.formatted.changePercent).toBe("+1.94%");
    });

    it("should calculate negative price change", () => {
      // Act
      const result = marketService.calculatePriceChange(177.0, 180.0);

      // Assert
      expect(result.change).toBe(-3.0);
      expect(result.changePercent).toBeCloseTo(-1.67, 1);
      expect(result.isPositive).toBe(false);
      expect(result.formatted.changePercent).toBe("-1.67%");
    });

    it("should handle zero price change", () => {
      // Act
      const result = marketService.calculatePriceChange(180.0, 180.0);

      // Assert
      expect(result.change).toBe(0);
      expect(result.changePercent).toBe(0);
      expect(result.isPositive).toBe(true);
      expect(result.formatted.changePercent).toBe("+0.00%");
    });

    it("should format change with absolute value", () => {
      // Act - negative change
      const result = marketService.calculatePriceChange(177.0, 180.0);

      // Assert - formatted.change should be absolute value
      expect(result.formatted.change).toContain("3.00");
    });
  });

  // ===== createDebouncedSearch Tests =====

  describe("createDebouncedSearch", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("should debounce search calls", async () => {
      // Arrange
      const debouncedSearch = marketService.createDebouncedSearch(300);
      const callback = vi.fn();
      const mockResponse = {
        data: { query: "AAPL", results: [] },
      };
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      // Act - Multiple rapid calls
      debouncedSearch("A", callback);
      debouncedSearch("AA", callback);
      debouncedSearch("AAP", callback);
      debouncedSearch("AAPL", callback);

      // Fast-forward time
      await vi.advanceTimersByTimeAsync(300);

      // Assert - Should only call once with final query
      expect(apiClient.get).toHaveBeenCalledTimes(1);
      expect(apiClient.get).toHaveBeenCalledWith("/api/market/search?q=AAPL");
    });

    it("should return empty results for query length < 1", () => {
      // Arrange
      const debouncedSearch = marketService.createDebouncedSearch(300);
      const callback = vi.fn();

      // Act
      debouncedSearch("", callback);

      // Assert
      expect(callback).toHaveBeenCalledWith({ query: "", results: [] });
      expect(apiClient.get).not.toHaveBeenCalled();
    });

    it("should handle search errors gracefully", async () => {
      // Arrange
      const debouncedSearch = marketService.createDebouncedSearch(300);
      const callback = vi.fn();
      const consoleErrorSpy = vi
        .spyOn(console, "error")
        .mockImplementation(() => {});
      vi.mocked(apiClient.get).mockRejectedValueOnce(
        new Error("Network error"),
      );

      // Act
      debouncedSearch("AAPL", callback);
      await vi.advanceTimersByTimeAsync(300);

      // Assert
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        "Symbol search error:",
        expect.any(Error),
      );
      expect(callback).toHaveBeenCalledWith({ query: "AAPL", results: [] });

      consoleErrorSpy.mockRestore();
    });

    it("should use custom delay", async () => {
      // Arrange
      const debouncedSearch = marketService.createDebouncedSearch(500);
      const callback = vi.fn();
      const mockResponse = {
        data: { query: "TSLA", results: [] },
      };
      vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

      // Act
      debouncedSearch("TSLA", callback);

      // Fast-forward 300ms (not enough)
      await vi.advanceTimersByTimeAsync(300);
      expect(apiClient.get).not.toHaveBeenCalled();

      // Fast-forward remaining 200ms
      await vi.advanceTimersByTimeAsync(200);

      // Assert
      expect(apiClient.get).toHaveBeenCalledTimes(1);
    });
  });

  // ===== Integration Tests =====

  describe("Integration - Complete workflow", () => {
    it("should perform full search-to-chart workflow", async () => {
      // Arrange - Mock search
      const searchResponse = {
        data: {
          query: "AAPL",
          results: [
            {
              symbol: "AAPL",
              name: "Apple Inc.",
              exchange: "NASDAQ",
              type: "Common Stock",
            },
          ],
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(searchResponse);

      // Arrange - Mock price data
      const priceResponse = {
        data: {
          symbol: "AAPL",
          interval: "5m",
          data: [
            {
              time: "2025-01-31T10:00:00",
              open: 180.0,
              high: 182.0,
              low: 179.5,
              close: 181.5,
              volume: 1000000,
            },
          ],
          last_updated: "2025-01-31T10:00:00Z",
        },
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce(priceResponse);

      // Act - Search
      const searchResults = await marketService.searchSymbols("AAPL");
      expect(searchResults.results[0].symbol).toBe("AAPL");

      // Act - Get recommended interval for 1d period
      const interval = marketService.getRecommendedInterval("1d");
      expect(interval).toBe("5m");

      // Act - Get price data
      const priceData = await marketService.getPriceData("AAPL", {
        interval,
        period: "1d",
      });
      expect(priceData.data).toHaveLength(1);

      // Act - Convert to chart format
      const chartData = marketService.convertToChartData(
        priceData.data,
        "candlestick",
      );
      expect(chartData[0]).toHaveProperty("open");
      expect(chartData[0]).toHaveProperty("close");
    });
  });
});
