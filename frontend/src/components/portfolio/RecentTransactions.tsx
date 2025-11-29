/**
 * Recent Transactions Component.
 *
 * Displays recent trading transactions (buy/sell orders) from MongoDB.
 * Includes both successful and failed orders with filtering support.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { apiClient } from "../../services/api";
import {
  ArrowUpCircle,
  ArrowDownCircle,
  Clock,
  DollarSign,
  AlertCircle,
  CheckCircle,
  XCircle,
  ChevronDown,
  Filter,
} from "lucide-react";

interface Transaction {
  order_id: string;
  alpaca_order_id: string | null;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  order_type: string;
  status: string;
  filled_qty: number;
  filled_avg_price: number | null;
  error_message: string | null; // For failed orders
  analysis_id: string | null;
  created_at: string | null;
  filled_at: string | null;
}

interface TransactionsResponse {
  transactions: Transaction[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

type StatusFilter = "all" | "success" | "failed";

/**
 * Fetch transactions from MongoDB
 */
async function fetchTransactions(
  limit: number,
  offset: number,
  status?: string
): Promise<TransactionsResponse> {
  const params: Record<string, unknown> = { limit, offset };
  if (status && status !== "all") {
    params.status = status;
  }
  const response = await apiClient.get<TransactionsResponse>(
    "/api/portfolio/transactions",
    { params }
  );
  return response.data;
}

export function RecentTransactions() {
  const { t } = useTranslation(["portfolio", "common"]);
  const [showAll, setShowAll] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const limit = showAll ? 100 : 10;

  const { data, isLoading, error } = useQuery({
    queryKey: ["recent-transactions", limit, statusFilter],
    queryFn: () => fetchTransactions(limit, 0, statusFilter),
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const getStatusIcon = (status: string) => {
    if (status === "failed") {
      return <XCircle size={14} className="text-red-500" />;
    }
    if (status === "filled") {
      return <CheckCircle size={14} className="text-green-500" />;
    }
    return <Clock size={14} className="text-yellow-500" />;
  };

  const getStatusColor = (status: string) => {
    if (status === "failed") {
      return "bg-red-100 text-red-800";
    }
    if (status === "filled") {
      return "bg-green-100 text-green-800";
    }
    return "bg-yellow-100 text-yellow-800";
  };

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
        <div className="text-sm text-red-500">
          {t("portfolio:transactions.loadFailed")}
        </div>
      </div>
    );
  }

  const transactions = data?.transactions || [];
  const total = data?.total || 0;
  const hasMore = data?.has_more || false;

  return (
    <div className="bg-white rounded-lg border border-gray-200">
      {/* Header with Filter */}
      <div className="px-4 py-3 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
            <Clock size={16} />
            {t("portfolio:transactions.title")}
          </h3>

          {/* Status Filter Dropdown */}
          <div className="relative">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              className="appearance-none pl-7 pr-6 py-1 text-xs border border-gray-200 rounded-md bg-white hover:bg-gray-50 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option value="all">{t("portfolio:transactions.filterAll")}</option>
              <option value="success">{t("portfolio:transactions.filterSuccess")}</option>
              <option value="failed">{t("portfolio:transactions.filterFailed")}</option>
            </select>
            <Filter
              size={12}
              className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
            />
            <ChevronDown
              size={12}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
            />
          </div>
        </div>
        <p className="text-xs text-gray-500 mt-1">
          {t("portfolio:transactions.subtitle", { count: total })}
        </p>
      </div>

      {/* Transactions List - Scrollable */}
      {transactions.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-8">
          {t("portfolio:transactions.noTransactions")}
        </div>
      ) : (
        <div
          className={`divide-y divide-gray-100 ${
            showAll ? "max-h-96 overflow-y-auto" : ""
          }`}
        >
          {transactions.map((transaction) => {
            const isBuy = transaction.side === "buy";
            const isFailed = transaction.status === "failed";
            const timestamp = transaction.filled_at || transaction.created_at;
            const displayTime = timestamp
              ? new Date(timestamp).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })
              : "-";

            const totalValue = transaction.filled_avg_price
              ? transaction.filled_qty * transaction.filled_avg_price
              : 0;

            return (
              <div
                key={transaction.order_id}
                className={`px-4 py-3 hover:bg-gray-50 transition-colors ${
                  isFailed ? "bg-red-50/30" : ""
                }`}
              >
                <div className="flex items-start gap-3">
                  {/* Icon */}
                  <div
                    className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                      isFailed
                        ? "bg-red-100"
                        : isBuy
                        ? "bg-green-100"
                        : "bg-orange-100"
                    }`}
                  >
                    {isFailed ? (
                      <AlertCircle size={16} className="text-red-600" />
                    ) : isBuy ? (
                      <ArrowUpCircle size={16} className="text-green-600" />
                    ) : (
                      <ArrowDownCircle size={16} className="text-orange-600" />
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
                            : "bg-orange-100 text-orange-800"
                        }`}
                      >
                        {isBuy
                          ? t("portfolio:transactions.buy")
                          : t("portfolio:transactions.sell")}
                      </span>
                    </div>

                    {/* Quantity and Price */}
                    <div className="mt-1 text-xs text-gray-600">
                      <span>
                        {transaction.quantity}{" "}
                        {transaction.quantity === 1 ? "share" : "shares"}
                      </span>
                      {transaction.filled_avg_price && (
                        <span className="ml-2">
                          @ ${transaction.filled_avg_price.toFixed(2)}
                        </span>
                      )}
                    </div>

                    {/* Total Value (for filled orders) */}
                    {totalValue > 0 && (
                      <div className="mt-1 flex items-center gap-1 text-xs font-medium text-gray-900">
                        <DollarSign size={12} />
                        {totalValue.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}
                      </div>
                    )}

                    {/* Error Message (for failed orders) */}
                    {isFailed && transaction.error_message && (
                      <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                        <span className="font-medium">Error: </span>
                        {transaction.error_message}
                      </div>
                    )}

                    {/* Timestamp */}
                    <div className="mt-1 text-xs text-gray-500">{displayTime}</div>
                  </div>

                  {/* Status Badge */}
                  <div className="flex-shrink-0">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded flex items-center gap-1 ${getStatusColor(
                        transaction.status
                      )}`}
                    >
                      {getStatusIcon(transaction.status)}
                      {transaction.status}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Show All / Show Less Footer */}
      {(hasMore || showAll) && (
        <div className="px-4 py-2 border-t border-gray-200 bg-gray-50">
          <button
            onClick={() => setShowAll(!showAll)}
            className="w-full text-center text-xs text-blue-600 hover:text-blue-800 font-medium"
          >
            {showAll
              ? t("portfolio:transactions.showLess")
              : t("portfolio:transactions.showAll", { total })}
          </button>
        </div>
      )}
    </div>
  );
}
