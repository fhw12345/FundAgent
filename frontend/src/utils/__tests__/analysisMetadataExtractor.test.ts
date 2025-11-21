/**
 * Unit tests for Analysis Metadata Extractor
 *
 * Tests extraction of visualization-critical data from analysis responses:
 * - Fibonacci metadata extraction (levels, swing points, trend direction)
 * - Stochastic metadata extraction (latest K/D, signals, crossovers)
 * - Defensive handling of missing/undefined data
 * - Signal detection (overbought, oversold, neutral)
 * - Crossover detection (bullish, bearish)
 */

import { describe, it, expect } from "vitest";
import type {
  FibonacciAnalysisResponse,
  StochasticAnalysisResponse,
} from "../../services/analysis";
import {
  extractFibonacciMetadata,
  extractStochasticMetadata,
  type FibonacciMetadata,
  type StochasticMetadata,
} from "../analysisMetadataExtractor";

// ===== Fibonacci Metadata Extraction Tests =====

describe("extractFibonacciMetadata", () => {
  it("should extract complete Fibonacci metadata", () => {
    // Arrange
    const analysis: FibonacciAnalysisResponse = {
      symbol: "AAPL",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      fibonacci_levels: [
        { level: 0.0, price: 150.0, percentage: "0.0%" },
        { level: 0.382, price: 160.0, percentage: "38.2%" },
        { level: 0.618, price: 170.0, percentage: "61.8%" },
        { level: 1.0, price: 180.0, percentage: "100.0%" },
      ],
      market_structure: {
        swing_high: { price: 180.0, date: "2025-01-31" },
        swing_low: { price: 150.0, date: "2025-01-01" },
        trend_direction: "uptrend" as const,
        trend_quality: "high" as const,
      },
      raw_data: {
        timeframe: "1d",
        top_trends: [
          { level: 0.618, price: 170.0 },
        ],
      },
      confidence_score: 0.85,
    };

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.symbol).toBe("AAPL");
    expect(metadata.timeframe).toBe("1d");
    expect(metadata.start_date).toBe("2025-01-01");
    expect(metadata.end_date).toBe("2025-01-31");
    expect(metadata.fibonacci_levels).toHaveLength(4);
    expect(metadata.swing_high).toEqual({ price: 180.0, date: "2025-01-31" });
    expect(metadata.swing_low).toEqual({ price: 150.0, date: "2025-01-01" });
    expect(metadata.trend_direction).toBe("uptrend");
    expect(metadata.confidence_score).toBe(0.85);
  });

  it("should include raw_data for top_trends", () => {
    // Arrange
    const analysis: FibonacciAnalysisResponse = {
      symbol: "TSLA",
      start_date: "2025-01-01",
      end_date: "2025-01-15",
      fibonacci_levels: [],
      raw_data: {
        timeframe: "1h",
        top_trends: [
          { level: 0.382, price: 250.0 },
          { level: 0.618, price: 260.0 },
        ],
      },
    };

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.raw_data).toBeDefined();
    expect(metadata.raw_data?.timeframe).toBe("1h");
    expect(metadata.raw_data?.top_trends).toHaveLength(2);
  });

  it("should handle missing symbol with empty string", () => {
    // Arrange
    const analysis = {
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.symbol).toBe("");
  });

  it("should default timeframe to 1d when missing", () => {
    // Arrange
    const analysis = {
      symbol: "AAPL",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.timeframe).toBe("1d");
  });

  it("should extract timeframe from raw_data", () => {
    // Arrange
    const analysis: FibonacciAnalysisResponse = {
      symbol: "GOOGL",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        timeframe: "15m",
      },
    };

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.timeframe).toBe("15m");
  });

  it("should handle missing fibonacci_levels with empty array", () => {
    // Arrange
    const analysis = {
      symbol: "MSFT",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.fibonacci_levels).toEqual([]);
  });

  it("should provide default swing_high when missing", () => {
    // Arrange
    const analysis = {
      symbol: "NVDA",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.swing_high).toEqual({ price: 0, date: "" });
  });

  it("should provide default swing_low when missing", () => {
    // Arrange
    const analysis = {
      symbol: "AMD",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.swing_low).toEqual({ price: 0, date: "" });
  });

  it("should default trend_direction to uptrend", () => {
    // Arrange
    const analysis = {
      symbol: "NFLX",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.trend_direction).toBe("uptrend");
  });

  it("should handle downtrend direction", () => {
    // Arrange
    const analysis: FibonacciAnalysisResponse = {
      symbol: "PYPL",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      market_structure: {
        swing_high: { price: 100.0, date: "2025-01-01" },
        swing_low: { price: 80.0, date: "2025-01-31" },
        trend_direction: "downtrend" as const,
        trend_quality: "medium" as const,
      },
    };

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.trend_direction).toBe("downtrend");
  });

  it("should handle missing confidence_score", () => {
    // Arrange
    const analysis = {
      symbol: "INTC",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as FibonacciAnalysisResponse;

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.confidence_score).toBeUndefined();
  });

  it("should handle empty raw_data", () => {
    // Arrange
    const analysis: FibonacciAnalysisResponse = {
      symbol: "BA",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {},
    };

    // Act
    const metadata = extractFibonacciMetadata(analysis);

    // Assert
    expect(metadata.raw_data).toEqual({});
    expect(metadata.timeframe).toBe("1d");
  });
});

// ===== Stochastic Metadata Extraction Tests =====

describe("extractStochasticMetadata", () => {
  it("should extract complete Stochastic metadata", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "AAPL",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [45, 50, 55, 60],
        stochastic_d: [40, 45, 50, 55],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.symbol).toBe("AAPL");
    expect(metadata.timeframe).toBe("1d");
    expect(metadata.start_date).toBe("2025-01-01");
    expect(metadata.end_date).toBe("2025-01-31");
    expect(metadata.current_k).toBe(60);
    expect(metadata.current_d).toBe(55);
  });

  it("should detect overbought signal (K > 80, D > 80)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "TSLA",
      timeframe: "1h",
      start_date: "2025-01-01",
      end_date: "2025-01-15",
      raw_data: {
        stochastic_k: [75, 80, 85],
        stochastic_d: [70, 78, 82],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(85);
    expect(metadata.current_d).toBe(82);
    expect(metadata.signal).toBe("overbought");
  });

  it("should detect oversold signal (K < 20, D < 20)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "GOOGL",
      timeframe: "15m",
      start_date: "2025-01-01",
      end_date: "2025-01-02",
      raw_data: {
        stochastic_k: [25, 20, 15],
        stochastic_d: [22, 18, 12],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(15);
    expect(metadata.current_d).toBe(12);
    expect(metadata.signal).toBe("oversold");
  });

  it("should detect neutral signal", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "MSFT",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [40, 45, 50],
        stochastic_d: [38, 42, 48],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.signal).toBe("neutral");
  });

  it("should detect bullish crossover (K crosses above D)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "NVDA",
      timeframe: "1h",
      start_date: "2025-01-01",
      end_date: "2025-01-15",
      raw_data: {
        stochastic_k: [45, 50, 55],
        stochastic_d: [48, 52, 50],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(55);
    expect(metadata.current_d).toBe(50);
    expect(metadata.crossover_signal).toBe("bullish");
  });

  it("should detect bearish crossover (K crosses below D)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "AMD",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [55, 50, 45], // K starts at 55, drops to 45
        stochastic_d: [48, 48, 50], // D stays around 48-50, prevK (50) > prevD (48), latestK (45) < latestD (50)
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(45);
    expect(metadata.current_d).toBe(50);
    expect(metadata.crossover_signal).toBe("bearish");
  });

  it("should return null crossover when no crossover detected", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "NFLX",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [45, 50, 55],
        stochastic_d: [40, 45, 50],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.crossover_signal).toBeNull();
  });

  it("should handle empty K/D arrays with defaults", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "PYPL",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [],
        stochastic_d: [],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(50);
    expect(metadata.current_d).toBe(50);
    expect(metadata.signal).toBe("neutral");
  });

  it("should handle missing raw_data with defaults", () => {
    // Arrange
    const analysis = {
      symbol: "INTC",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as StochasticAnalysisResponse;

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(50);
    expect(metadata.current_d).toBe(50);
    expect(metadata.signal).toBe("neutral");
    expect(metadata.crossover_signal).toBeNull();
  });

  it("should handle single value in K/D arrays (no crossover)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "BA",
      timeframe: "1h",
      start_date: "2025-01-01",
      end_date: "2025-01-02",
      raw_data: {
        stochastic_k: [65],
        stochastic_d: [60],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.current_k).toBe(65);
    expect(metadata.current_d).toBe(60);
    expect(metadata.crossover_signal).toBeNull();
  });

  it("should handle missing symbol with empty string", () => {
    // Arrange
    const analysis = {
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as StochasticAnalysisResponse;

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.symbol).toBe("");
  });

  it("should default timeframe to 1d when missing", () => {
    // Arrange
    const analysis = {
      symbol: "DIS",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
    } as StochasticAnalysisResponse;

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.timeframe).toBe("1d");
  });

  it("should handle edge case: K=80.1, D=79.9 (not overbought)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "V",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [80.1],
        stochastic_d: [79.9],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.signal).toBe("neutral"); // Both must be > 80
  });

  it("should handle edge case: K=19.9, D=20.1 (not oversold)", () => {
    // Arrange
    const analysis: StochasticAnalysisResponse = {
      symbol: "MA",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      raw_data: {
        stochastic_k: [19.9],
        stochastic_d: [20.1],
      },
    };

    // Act
    const metadata = extractStochasticMetadata(analysis);

    // Assert
    expect(metadata.signal).toBe("neutral"); // Both must be < 20
  });
});

// ===== Type Tests =====

describe("Type definitions", () => {
  it("FibonacciMetadata should have correct structure", () => {
    // Arrange
    const metadata: FibonacciMetadata = {
      symbol: "TEST",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      fibonacci_levels: [],
      swing_high: { price: 100, date: "2025-01-31" },
      swing_low: { price: 80, date: "2025-01-01" },
      trend_direction: "uptrend",
    };

    // Assert - TypeScript compilation succeeds
    expect(metadata.symbol).toBe("TEST");
    expect(metadata.trend_direction).toBe("uptrend");
  });

  it("StochasticMetadata should have correct structure", () => {
    // Arrange
    const metadata: StochasticMetadata = {
      symbol: "TEST",
      timeframe: "1d",
      start_date: "2025-01-01",
      end_date: "2025-01-31",
      current_k: 50,
      current_d: 45,
      signal: "neutral",
      crossover_signal: null,
    };

    // Assert - TypeScript compilation succeeds
    expect(metadata.symbol).toBe("TEST");
    expect(metadata.signal).toBe("neutral");
  });
});
