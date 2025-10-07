/**
 * Metadata validation utilities
 *
 * Validates analysis metadata before using it for chart overlays.
 * Prevents broken UI from empty or malformed metadata.
 */

import type {
  FibonacciMetadata,
  StochasticMetadata,
} from "./analysisMetadataExtractor";

/**
 * Type guard: Check if Fibonacci metadata is valid and usable.
 */
export function isValidFibonacciMetadata(
  metadata: FibonacciMetadata | null | undefined,
): metadata is FibonacciMetadata {
  if (!metadata) return false;

  // Must have symbol and timeframe
  if (!metadata.symbol || !metadata.timeframe) return false;

  // Must have fibonacci levels array with at least one level
  if (
    !Array.isArray(metadata.fibonacci_levels) ||
    metadata.fibonacci_levels.length === 0
  ) {
    return false;
  }

  // Verify each level has required fields
  return metadata.fibonacci_levels.every(
    (level) =>
      typeof level.level === "number" &&
      typeof level.price === "number" &&
      typeof level.percentage === "string",
  );
}

/**
 * Type guard: Check if Stochastic metadata is valid and usable.
 */
export function isValidStochasticMetadata(
  metadata: StochasticMetadata | null | undefined,
): metadata is StochasticMetadata {
  if (!metadata) return false;

  // Must have symbol and timeframe
  if (!metadata.symbol || !metadata.timeframe) return false;

  // Must have current K and D values (numbers between 0-100)
  if (
    typeof metadata.current_k !== "number" ||
    typeof metadata.current_d !== "number"
  ) {
    return false;
  }

  // Values should be in valid range
  if (
    metadata.current_k < 0 ||
    metadata.current_k > 100 ||
    metadata.current_d < 0 ||
    metadata.current_d > 100
  ) {
    return false;
  }

  // Must have valid signal
  if (
    !metadata.signal ||
    !["overbought", "oversold", "neutral"].includes(metadata.signal)
  ) {
    return false;
  }

  return true;
}

/**
 * Check if object is empty or has no meaningful data.
 * Used to filter out empty metadata objects.
 */
export function isEmptyMetadata(metadata: any): boolean {
  if (!metadata) return true;
  if (typeof metadata !== "object") return true;
  if (Object.keys(metadata).length === 0) return true;

  // Check if all values are null/undefined
  return Object.values(metadata).every(
    (value) => value === null || value === undefined,
  );
}

/**
 * Extract analysis type from metadata.
 * Returns "fibonacci", "stochastic", or null.
 */
export function getAnalysisType(
  metadata: any,
): "fibonacci" | "stochastic" | null {
  if (isValidFibonacciMetadata(metadata)) {
    return "fibonacci";
  }
  if (isValidStochasticMetadata(metadata)) {
    return "stochastic";
  }
  return null;
}
