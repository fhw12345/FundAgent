/**
 * TypeScript types for credit economy system.
 */

// ===== User Profile with Credits =====

export interface UserProfile {
  user_id: string;
  username: string;
  email: string | null;
  credits: number;
  total_tokens_used: number;
  total_credits_spent: number;
  created_at: string;
}

// ===== Credit Transaction =====

export type TransactionStatus = "PENDING" | "COMPLETED" | "FAILED";

export interface CreditTransaction {
  transaction_id: string;
  user_id: string;
  chat_id: string;
  message_id: string | null;
  status: TransactionStatus;
  estimated_cost: number;
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
  actual_cost: number | null;
  created_at: string;
  completed_at: string | null;
  model: string;
  request_type: string;
}

// ===== API Responses =====

export interface TransactionHistoryResponse {
  transactions: CreditTransaction[];
  pagination: {
    page: number;
    page_size: number;
    total: number;
    total_pages: number;
  };
}

export interface CreditAdjustmentRequest {
  user_id: string;
  amount: number;
  reason: string;
}

export interface CreditAdjustmentResponse {
  user_id: string;
  old_balance: number;
  adjustment: number;
  new_balance: number;
  reason: string;
}

// ===== Frontend-only Types =====

/**
 * Optimistic credit state for immediate UI updates
 */
export interface OptimisticCreditState {
  balance: number;
  lastUpdate: Date;
  pendingDeduction: number | null;
}
