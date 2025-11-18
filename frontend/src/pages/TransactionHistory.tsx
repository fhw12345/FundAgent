/**
 * Transaction History page.
 * Displays paginated credit transaction history with filtering.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { History, ArrowLeft, Filter, CheckCircle, XCircle, Clock } from "lucide-react";
import { useTransactionHistory } from "../hooks/useCredits";
import type { TransactionStatus } from "../types/credits";

export function TransactionHistory() {
  const { t, i18n } = useTranslation(['chat', 'common']);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<TransactionStatus | undefined>(undefined);

  const { data, isLoading, isError } = useTransactionHistory(page, 20, statusFilter);

  const getStatusIcon = (status: TransactionStatus) => {
    switch (status) {
      case "COMPLETED":
        return <CheckCircle size={16} className="text-green-600" />;
      case "FAILED":
        return <XCircle size={16} className="text-red-600" />;
      case "PENDING":
        return <Clock size={16} className="text-orange-600" />;
    }
  };

  const getStatusColor = (status: TransactionStatus) => {
    switch (status) {
      case "COMPLETED":
        return "bg-green-50 text-green-700 border-green-200";
      case "FAILED":
        return "bg-red-50 text-red-700 border-red-200";
      case "PENDING":
        return "bg-orange-50 text-orange-700 border-orange-200";
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString(i18n.language === 'zh-CN' ? 'zh-CN' : 'en-US', {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50/30 to-purple-50 p-6">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => window.history.back()}
              className="p-2 hover:bg-white/60 rounded-lg transition-all"
            >
              <ArrowLeft size={20} className="text-gray-600" />
            </button>
            <h1 className="text-xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent">
              {t('chat:transactions.title')}
            </h1>
          </div>

          {/* Filter */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 text-sm text-gray-600">
              <Filter size={16} />
              <span>{t('common:buttons.filter')}:</span>
            </div>
            <select
              value={statusFilter ?? "all"}
              onChange={(e) => {
                setStatusFilter(e.target.value === "all" ? undefined : e.target.value as TransactionStatus);
                setPage(1); // Reset to first page on filter change
              }}
              className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white/60 hover:bg-white/80 transition-all text-sm"
            >
              <option value="all">{t('chat:transactions.allTransactions')}</option>
              <option value="COMPLETED">{t('common:status.completed')}</option>
              <option value="PENDING">{t('common:status.pending')}</option>
              <option value="FAILED">{t('common:status.failed')}</option>
            </select>
          </div>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="p-4 rounded-xl bg-white/60 border border-gray-200/50 animate-pulse"
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-1/4"></div>
                    <div className="h-3 bg-gray-200 rounded w-1/3"></div>
                  </div>
                  <div className="h-6 bg-gray-200 rounded w-20"></div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-6 rounded-xl bg-red-50/80 border border-red-200/50">
            <p className="text-red-600 font-medium">{t('chat:transactions.loadFailed')}</p>
          </div>
        )}

        {/* Transactions List */}
        {data && (
          <>
            <div className="space-y-3 mb-6">
              {data.transactions.length === 0 ? (
                <div className="p-12 rounded-xl bg-white/60 border border-gray-200/50 text-center">
                  <History size={48} className="mx-auto mb-3 text-gray-400" />
                  <p className="text-gray-600 font-medium">{t('chat:transactions.noTransactions')}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {statusFilter ? t('chat:transactions.tryChangingFilter') : t('chat:transactions.startChatToSee')}
                  </p>
                </div>
              ) : (
                data.transactions.map((transaction) => (
                  <div
                    key={transaction.transaction_id}
                    className="p-4 rounded-xl bg-white/60 border border-gray-200/50 hover:bg-white/80 transition-all"
                  >
                    <div className="flex items-start justify-between gap-4">
                      {/* Left: Transaction Details */}
                      <div className="flex-1 space-y-2">
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium border flex items-center gap-1 ${getStatusColor(transaction.status)}`}
                          >
                            {getStatusIcon(transaction.status)}
                            {transaction.status}
                          </span>
                          <span className="text-xs text-gray-500">{transaction.transaction_id}</span>
                        </div>

                        <div className="text-sm space-y-1">
                          <div className="flex items-center gap-4 text-gray-700">
                            <span className="font-medium">{t('chat:transactions.model')}:</span>
                            <span className="text-gray-600">{transaction.model}</span>
                          </div>

                          {transaction.status === "COMPLETED" && transaction.total_tokens !== null && (
                            <div className="flex items-center gap-4 text-gray-700">
                              <span className="font-medium">{t('chat:transactions.tokens')}:</span>
                              <span className="text-gray-600">
                                {transaction.input_tokens} {t('chat:transactions.in')} / {transaction.output_tokens} {t('chat:transactions.out')} = {transaction.total_tokens} {t('chat:transactions.total')}
                              </span>
                            </div>
                          )}

                          <div className="flex items-center gap-4 text-gray-700">
                            <span className="font-medium">{t('common:labels.date')}:</span>
                            <span className="text-gray-600">{formatDate(transaction.created_at)}</span>
                          </div>
                        </div>
                      </div>

                      {/* Right: Cost */}
                      <div className="text-right">
                        {transaction.status === "COMPLETED" && transaction.actual_cost !== null ? (
                          <>
                            <p className="text-2xl font-bold text-gray-900">
                              {transaction.actual_cost.toFixed(2)}
                            </p>
                            <p className="text-xs text-gray-500">{t('chat:transactions.creditsUnit')}</p>
                          </>
                        ) : transaction.status === "PENDING" ? (
                          <>
                            <p className="text-lg font-semibold text-orange-600">~{transaction.estimated_cost.toFixed(2)}</p>
                            <p className="text-xs text-gray-500">{t('chat:transactions.estimated')}</p>
                          </>
                        ) : (
                          <p className="text-sm text-gray-500">{t('chat:transactions.noCharge')}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Pagination */}
            {data.pagination.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 bg-white/60 rounded-xl border border-gray-200/50">
                <div className="text-sm text-gray-600">
                  {t('common:pagination.page')} {data.pagination.page} {t('common:pagination.of')} {data.pagination.total_pages}
                  {" • "}
                  {data.pagination.total} {t('chat:transactions.totalTransactions')}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white/60 hover:bg-white/80 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm font-medium"
                  >
                    {t('common:buttons.previous')}
                  </button>
                  <button
                    onClick={() => setPage((p) => Math.min(data.pagination.total_pages, p + 1))}
                    disabled={page === data.pagination.total_pages}
                    className="px-3 py-1.5 rounded-lg border border-gray-200 bg-white/60 hover:bg-white/80 disabled:opacity-50 disabled:cursor-not-allowed transition-all text-sm font-medium"
                  >
                    {t('common:buttons.next')}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
