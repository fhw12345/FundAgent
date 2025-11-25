/**
 * Recent Transactions Component.
 *
 * Displays recent Alpaca trading transactions (buy/sell orders)
 * sorted from latest to oldest.
 */

import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { apiClient } from "../../services/api";
import { ArrowUpCircle, ArrowDownCircle, Clock, DollarSign } from "lucide-react";

interface Transaction {
  order_id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  filled_avg_price: number | null;
  status: string;
  submitted_at: string | null;  // When order was submitted to Alpaca
  filled_at: string | null;     // When order was executed
}

interface TransactionsResponse {
  orders: Transaction[];
  total: number;
}

/**
 * Fetch recent Alpaca transactions
 */
async function fetchRecentTransactions(limit: number = 10): Promise<TransactionsResponse> {
  const response = await apiClient.get<TransactionsResponse>(
    "/api/portfolio/orders",
    {
      params: { limit, status: "filled" }, // Only show filled orders
    }
  );
  return response.data;
}

export function RecentTransactions() {
  const { t } = useTranslation(["portfolio", "common"]);

  const { data, isLoading, error } = useQuery({
    queryKey: ["recent-transactions"],
    queryFn: () => fetchRecentTransactions(10),
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Clock size={16} />
          {t("portfolio:transactions.title")}
        </h3>
        <div className="flex items-center justify-center py-8">
          <div className="text-sm text-gray-500">{t("common:loading")}</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Clock size={16} />
          {t("portfolio:transactions.title")}
        </h3>
        <div className="text-sm text-red-500">{t("portfolio:transactions.loadFailed")}</div>
      </div>
    );
  }

  const transactions = data?.orders || [];

  if (transactions.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <Clock size={16} />
          {t("portfolio:transactions.title")}
        </h3>
        <div className="text-sm text-gray-500 text-center py-8">
          {t("portfolio:transactions.noTransactions")}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
          <Clock size={16} />
          {t("portfolio:transactions.title")}
        </h3>
        <p className="text-xs text-gray-500 mt-1">
          {t("portfolio:transactions.subtitle", { count: transactions.length })}
        </p>
      </div>

      {/* Transactions List */}
      <div className="divide-y divide-gray-100">
        {transactions.map((transaction) => {
          const isBuy = transaction.side === "buy";
          const timestamp = transaction.filled_at || transaction.submitted_at;
          const displayTime = new Date(timestamp).toLocaleString("en-US", {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit",
          });

          const totalValue = transaction.filled_avg_price
            ? transaction.quantity * transaction.filled_avg_price
            : 0;

          return (
            <div
              key={transaction.order_id}
              className="px-4 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-start gap-3">
                {/* Icon */}
                <div
                  className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                    isBuy ? "bg-green-100" : "bg-red-100"
                  }`}
                >
                  {isBuy ? (
                    <ArrowUpCircle size={16} className="text-green-600" />
                  ) : (
                    <ArrowDownCircle size={16} className="text-red-600" />
                  )}
                </div>

                {/* Transaction Info */}
                <div className="flex-1 min-w-0">
                  {/* Symbol and Side */}
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm text-gray-900">
                      {transaction.symbol}
                    </span>
                    <span
                      className={`px-2 py-0.5 text-xs font-medium rounded ${
                        isBuy
                          ? "bg-green-100 text-green-800"
                          : "bg-red-100 text-red-800"
                      }`}
                    >
                      {isBuy ? t("portfolio:transactions.buy") : t("portfolio:transactions.sell")}
                    </span>
                  </div>

                  {/* Quantity and Price */}
                  <div className="mt-1 text-xs text-gray-600">
                    <span>
                      {transaction.quantity} {transaction.quantity === 1 ? "share" : "shares"}
                    </span>
                    {transaction.filled_avg_price && (
                      <span className="ml-2">
                        @ ${transaction.filled_avg_price.toFixed(2)}
                      </span>
                    )}
                  </div>

                  {/* Total Value */}
                  {totalValue > 0 && (
                    <div className="mt-1 flex items-center gap-1 text-xs font-medium text-gray-900">
                      <DollarSign size={12} />
                      {totalValue.toLocaleString("en-US", {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                      })}
                    </div>
                  )}

                  {/* Timestamp */}
                  <div className="mt-1 text-xs text-gray-500">{displayTime}</div>
                </div>

                {/* Status Badge */}
                <div className="flex-shrink-0">
                  <span className="px-2 py-1 text-xs font-medium rounded bg-blue-100 text-blue-800">
                    {transaction.status}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
