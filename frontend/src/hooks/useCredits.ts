/**
 * React Query hooks for credit system.
 * Handles user profile, transaction history, and optimistic credit updates.
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type {
  UserProfile,
  CreditAdjustmentRequest,
} from "../types/credits";
import { creditService } from "../services/api";

// ===== Query Keys =====

export const creditKeys = {
  all: ["credits"] as const,
  profile: () => [...creditKeys.all, "profile"] as const,
  transactions: () => [...creditKeys.all, "transactions"] as const,
  transactionList: (page: number, status?: string) =>
    [...creditKeys.transactions(), { page, status }] as const,
};

// ===== Hooks =====

/**
 * Hook to fetch user profile with credit balance.
 * Refetches every 30 seconds to keep balance in sync with backend.
 */
export function useUserProfile() {
  return useQuery({
    queryKey: creditKeys.profile(),
    queryFn: () => creditService.getUserProfile(),
    staleTime: 30 * 1000, // 30 seconds
    gcTime: 5 * 60 * 1000, // 5 minutes
    refetchInterval: 30 * 1000, // Refetch every 30 seconds
    refetchOnWindowFocus: true, // Refetch when user returns to tab
  });
}

/**
 * Hook to fetch paginated transaction history
 */
export function useTransactionHistory(
  page: number = 1,
  pageSize: number = 20,
  status?: string,
) {
  return useQuery({
    queryKey: creditKeys.transactionList(page, status),
    queryFn: () => creditService.getTransactionHistory(page, pageSize, status),
    staleTime: 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Hook to adjust user credits (admin only)
 */
export function useAdjustCredits() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreditAdjustmentRequest) =>
      creditService.adjustCredits(request),

    // On success, invalidate profile and transaction history
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: creditKeys.profile() });
      void queryClient.invalidateQueries({
        queryKey: creditKeys.transactions(),
      });
    },
  });
}

/**
 * Hook to optimistically deduct credits before LLM call.
 * Updates cache immediately, then syncs with backend via refetch.
 * Provides rollback function if operation fails.
 *
 * @returns Object with deduct and rollback functions
 */
export function useOptimisticCreditDeduction() {
  const queryClient = useQueryClient();

  return {
    deduct: (estimatedCost: number) => {
      // Get current profile from cache
      const currentProfile = queryClient.getQueryData<UserProfile>(
        creditKeys.profile(),
      );

      if (!currentProfile) {
        console.warn("No user profile in cache - cannot optimistically deduct");
        return { rollback: () => {} };
      }

      // Save original for potential rollback
      const originalProfile = currentProfile;

      // Optimistically deduct credits
      const optimisticProfile: UserProfile = {
        ...currentProfile,
        credits: Math.max(0, currentProfile.credits - estimatedCost),
      };

      queryClient.setQueryData<UserProfile>(
        creditKeys.profile(),
        optimisticProfile,
      );

      // Trigger refetch in background (backend is source of truth)
      void queryClient.invalidateQueries({ queryKey: creditKeys.profile() });

      // Return rollback function
      return {
        rollback: () => {
          queryClient.setQueryData<UserProfile>(
            creditKeys.profile(),
            originalProfile,
          );
          console.warn("Credit deduction rolled back");
        },
      };
    },
  };
}

/**
 * Hook to manually trigger profile refetch (for error recovery)
 */
export function useRefreshProfile() {
  const queryClient = useQueryClient();

  return () => {
    void queryClient.invalidateQueries({ queryKey: creditKeys.profile() });
  };
}

/**
 * Hook to get current credit balance from cache (no network request)
 */
export function useCurrentBalance(): number | null {
  const queryClient = useQueryClient();
  const profile = queryClient.getQueryData<UserProfile>(creditKeys.profile());
  return profile?.credits ?? null;
}
