/**
 * React Query hooks for Market Insights Platform.
 * Provides data fetching, caching, and mutation capabilities.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as insightsApi from "../services/insightsApi";
import type {
  CategoriesListResponse,
  CompositeScore,
  InsightCategory,
  InsightMetric,
  TrendResponse,
} from "../types/insights";

/**
 * Query key factory for insights data.
 * Structured namespace prevents cache collisions.
 */
export const insightsKeys = {
  all: ["insights"] as const,
  categories: () => [...insightsKeys.all, "categories"] as const,
  category: (id: string) => [...insightsKeys.all, "category", id] as const,
  composite: (id: string) => [...insightsKeys.all, "composite", id] as const,
  metric: (categoryId: string, metricId: string) =>
    [...insightsKeys.all, "metric", categoryId, metricId] as const,
  trend: (categoryId: string, days: number) =>
    [...insightsKeys.all, "trend", categoryId, days] as const,
};

/**
 * Hook to fetch all available insight categories.
 * Returns lightweight metadata for the categories list view.
 */
export function useCategories() {
  return useQuery<CategoriesListResponse>({
    queryKey: insightsKeys.categories(),
    queryFn: insightsApi.getCategories,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Hook to fetch complete category data with all metrics.
 *
 * @param categoryId - Category identifier
 * @param enabled - Optional flag to conditionally enable the query
 */
export function useCategory(categoryId: string, enabled: boolean = true) {
  return useQuery<InsightCategory>({
    queryKey: insightsKeys.category(categoryId),
    queryFn: () => insightsApi.getCategory(categoryId, false),
    staleTime: 2 * 60 * 1000, // 2 minutes
    gcTime: 15 * 60 * 1000, // 15 minutes
    enabled: enabled && !!categoryId,
  });
}

/**
 * Hook to fetch just the composite score for a category.
 * Lighter-weight alternative when full metrics aren't needed.
 *
 * @param categoryId - Category identifier
 */
export function useCompositeScore(categoryId: string) {
  return useQuery<CompositeScore>({
    queryKey: insightsKeys.composite(categoryId),
    queryFn: () => insightsApi.getCompositeScore(categoryId),
    staleTime: 2 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    enabled: !!categoryId,
  });
}

/**
 * Hook to fetch a single metric with full explanation.
 *
 * @param categoryId - Category identifier
 * @param metricId - Metric identifier
 */
export function useMetric(categoryId: string, metricId: string) {
  return useQuery<InsightMetric>({
    queryKey: insightsKeys.metric(categoryId, metricId),
    queryFn: () => insightsApi.getMetric(categoryId, metricId),
    staleTime: 2 * 60 * 1000,
    gcTime: 15 * 60 * 1000,
    enabled: !!categoryId && !!metricId,
  });
}

/**
 * Hook to fetch historical trend data for a category.
 * Returns composite and individual metric trends over time.
 *
 * @param categoryId - Category identifier
 * @param days - Number of days of history (default: 30)
 */
export function useInsightTrend(categoryId: string, days: number = 30) {
  return useQuery<TrendResponse>({
    queryKey: insightsKeys.trend(categoryId, days),
    queryFn: () => insightsApi.getTrend(categoryId, days),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
    enabled: !!categoryId,
  });
}

/**
 * Options for the refresh category hook.
 */
interface UseRefreshCategoryOptions {
  /** Callback fired on successful refresh */
  onSuccess?: (data: insightsApi.RefreshResponse) => void;
  /** Callback fired on refresh error */
  onError?: (error: Error) => void;
}

/**
 * Hook to force refresh a category's data.
 * Invalidates cache and triggers recalculation.
 *
 * @param options - Optional callbacks for success/error handling
 */
export function useRefreshCategory(options: UseRefreshCategoryOptions = {}) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (categoryId: string) => insightsApi.refreshCategory(categoryId),
    onSuccess: (data) => {
      // Invalidate the specific category's cache
      void queryClient.invalidateQueries({
        queryKey: insightsKeys.category(data.category_id),
      });
      void queryClient.invalidateQueries({
        queryKey: insightsKeys.composite(data.category_id),
      });
      // Also refresh the categories list to update last_updated
      void queryClient.invalidateQueries({
        queryKey: insightsKeys.categories(),
      });
      // Call user-provided success callback
      options.onSuccess?.(data);
    },
    onError: (error: Error) => {
      // Call user-provided error callback
      options.onError?.(error);
    },
  });
}
