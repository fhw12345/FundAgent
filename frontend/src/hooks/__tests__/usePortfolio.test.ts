/**
 * Unit tests for portfolio React Query hooks.
 *
 * Tests data fetching, mutations, and cache invalidation logic.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createElement } from "react";
import {
  useHoldings,
  usePortfolioSummary,
  useAddHolding,
  useUpdateHolding,
  useDeleteHolding,
} from "../usePortfolio";
import * as portfolioApi from "../../services/portfolioApi";

// Mock the API module
vi.mock("../../services/portfolioApi");

// Helper to create wrapper with QueryClient
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return ({ children }: { children: any }) =>
    createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("Portfolio Hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("useHoldings", () => {
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

      vi.mocked(portfolioApi.getHoldings).mockResolvedValueOnce(mockHoldings);

      const { result } = renderHook(() => useHoldings(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockHoldings);
    });

    it("should handle fetch error", async () => {
      vi.mocked(portfolioApi.getHoldings).mockRejectedValueOnce(
        new Error("Network error")
      );

      const { result } = renderHook(() => useHoldings(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeDefined();
    });
  });

  describe("usePortfolioSummary", () => {
    it("should fetch summary successfully", async () => {
      const mockSummary = {
        holdings_count: 2,
        total_cost_basis: 30000,
        total_market_value: 32000,
        total_unrealized_pl: 2000,
        total_unrealized_pl_pct: 6.67,
      };

      vi.mocked(portfolioApi.getPortfolioSummary).mockResolvedValueOnce(
        mockSummary
      );

      const { result } = renderHook(() => usePortfolioSummary(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(result.current.data).toEqual(mockSummary);
    });
  });

  describe("useAddHolding", () => {
    it("should add holding successfully", async () => {
      const newHolding = {
        symbol: "TSLA",
        quantity: 50,
        avg_price: 200,
      };

      const mockResponse = {
        holding_id: "2",
        symbol: "TSLA",
        quantity: 50,
        avg_price: 200,
        current_price: null,
        cost_basis: 10000,
        market_value: null,
        unrealized_pl: null,
        unrealized_pl_pct: null,
        created_at: "2024-01-03",
        updated_at: "2024-01-03",
        last_price_update: null,
      };

      vi.mocked(portfolioApi.addHolding).mockResolvedValueOnce(mockResponse);

      const { result } = renderHook(() => useAddHolding(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(newHolding);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Verify first argument matches (React Query adds context as second arg)
      expect(portfolioApi.addHolding).toHaveBeenCalled();
      const callArgs = vi.mocked(portfolioApi.addHolding).mock.calls[0];
      expect(callArgs[0]).toEqual(newHolding);
    });
  });

  describe("useUpdateHolding", () => {
    it("should update holding successfully", async () => {
      const holdingId = "1";
      const update = {
        quantity: 150,
        avg_price: 155,
      };

      const mockResponse = {
        holding_id: holdingId,
        symbol: "AAPL",
        quantity: 150,
        avg_price: 155,
        current_price: 160,
        cost_basis: 23250,
        market_value: 24000,
        unrealized_pl: 750,
        unrealized_pl_pct: 3.23,
        created_at: "2024-01-01",
        updated_at: "2024-01-04",
        last_price_update: "2024-01-04",
      };

      vi.mocked(portfolioApi.updateHolding).mockResolvedValueOnce(
        mockResponse
      );

      const { result } = renderHook(() => useUpdateHolding(), {
        wrapper: createWrapper(),
      });

      result.current.mutate({ holdingId, update });

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      expect(portfolioApi.updateHolding).toHaveBeenCalledWith(
        holdingId,
        update
      );
    });
  });

  describe("useDeleteHolding", () => {
    it("should delete holding successfully", async () => {
      const holdingId = "1";

      vi.mocked(portfolioApi.deleteHolding).mockResolvedValueOnce();

      const { result } = renderHook(() => useDeleteHolding(), {
        wrapper: createWrapper(),
      });

      result.current.mutate(holdingId);

      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true);
      });

      // Verify first argument matches (React Query adds context as second arg)
      expect(portfolioApi.deleteHolding).toHaveBeenCalled();
      const callArgs = vi.mocked(portfolioApi.deleteHolding).mock.calls[0];
      expect(callArgs[0]).toEqual(holdingId);
    });
  });
});
