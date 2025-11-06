/**
 * Unit tests for portfolio API client.
 *
 * Tests API interactions, formatting helpers, and error handling.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import * as portfolioApi from "../portfolioApi";
import { apiClient } from "../api";

// Mock the API client
vi.mock("../api", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

describe("Portfolio API Client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getHoldings", () => {
    it("should fetch holdings successfully", async () => {
      const mockHoldings = [
        {
          holding_id: "1",
          symbol: "AAPL",
          quantity: 100,
          avg_price: 150,
          current_price: 160,
          cost_basis: 15000,
          market_value: 16000,
          unrealized_pl: 1000,
          unrealized_pl_pct: 6.67,
          created_at: "2024-01-01",
          updated_at: "2024-01-02",
          last_price_update: "2024-01-02",
        },
      ];

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockHoldings });

      const result = await portfolioApi.getHoldings();

      expect(apiClient.get).toHaveBeenCalledWith("/api/portfolio/holdings");
      expect(result).toEqual(mockHoldings);
    });
  });

  describe("getPortfolioSummary", () => {
    it("should fetch portfolio summary successfully", async () => {
      const mockSummary = {
        holdings_count: 2,
        total_cost_basis: 30000,
        total_market_value: 32000,
        total_unrealized_pl: 2000,
        total_unrealized_pl_pct: 6.67,
      };

      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSummary });

      const result = await portfolioApi.getPortfolioSummary();

      expect(apiClient.get).toHaveBeenCalledWith("/api/portfolio/summary");
      expect(result).toEqual(mockSummary);
    });
  });

  describe("addHolding", () => {
    it("should add holding successfully", async () => {
      const newHolding = {
        symbol: "TSLA",
        quantity: 50,
        avg_price: 200,
      };

      const mockResponse = {
        holding_id: "2",
        ...newHolding,
        current_price: null,
        cost_basis: 10000,
        market_value: null,
        unrealized_pl: null,
        unrealized_pl_pct: null,
        created_at: "2024-01-03",
        updated_at: "2024-01-03",
        last_price_update: null,
      };

      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: mockResponse });

      const result = await portfolioApi.addHolding(newHolding);

      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/portfolio/holdings",
        newHolding
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("updateHolding", () => {
    it("should update holding successfully", async () => {
      const holdingId = "1";
      const update = {
        quantity: 150,
        avg_price: 155,
      };

      const mockResponse = {
        holding_id: holdingId,
        symbol: "AAPL",
        ...update,
        current_price: 160,
        cost_basis: 23250,
        market_value: 24000,
        unrealized_pl: 750,
        unrealized_pl_pct: 3.23,
        created_at: "2024-01-01",
        updated_at: "2024-01-04",
        last_price_update: "2024-01-04",
      };

      vi.mocked(apiClient.patch).mockResolvedValueOnce({ data: mockResponse });

      const result = await portfolioApi.updateHolding(holdingId, update);

      expect(apiClient.patch).toHaveBeenCalledWith(
        `/api/portfolio/holdings/${holdingId}`,
        update
      );
      expect(result).toEqual(mockResponse);
    });
  });

  describe("deleteHolding", () => {
    it("should delete holding successfully", async () => {
      const holdingId = "1";

      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: undefined });

      await portfolioApi.deleteHolding(holdingId);

      expect(apiClient.delete).toHaveBeenCalledWith(
        `/api/portfolio/holdings/${holdingId}`
      );
    });
  });

  describe("formatPL", () => {
    it("should format positive P/L correctly", () => {
      const result = portfolioApi.formatPL(1000, 10.5);
      expect(result).toBe("+$1000.00 (+10.50%)");
    });

    it("should format negative P/L correctly", () => {
      const result = portfolioApi.formatPL(-500, -5.25);
      expect(result).toBe("$500.00 (-5.25%)");
    });

    it("should format zero P/L correctly", () => {
      const result = portfolioApi.formatPL(0, 0);
      expect(result).toBe("+$0.00 (+0.00%)");
    });

    it("should return N/A for null values", () => {
      expect(portfolioApi.formatPL(null, 5)).toBe("N/A");
      expect(portfolioApi.formatPL(100, null)).toBe("N/A");
      expect(portfolioApi.formatPL(null, null)).toBe("N/A");
    });
  });

  describe("getPLColor", () => {
    it("should return green for positive P/L", () => {
      expect(portfolioApi.getPLColor(100)).toBe("green");
      expect(portfolioApi.getPLColor(0.01)).toBe("green");
    });

    it("should return red for negative P/L", () => {
      expect(portfolioApi.getPLColor(-100)).toBe("red");
      expect(portfolioApi.getPLColor(-0.01)).toBe("red");
    });

    it("should return gray for zero or null P/L", () => {
      expect(portfolioApi.getPLColor(0)).toBe("gray");
      expect(portfolioApi.getPLColor(null)).toBe("gray");
    });
  });
});
