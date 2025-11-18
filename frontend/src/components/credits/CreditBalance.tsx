/**
 * Credit balance display component.
 * Shows user's current credit balance with glassmorphism design.
 * Optimistically updates on LLM calls, syncs every 30s with backend.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Coins, TrendingUp, AlertCircle, Eye, EyeOff } from "lucide-react";
import { useUserProfile } from "../../hooks/useCredits";

interface CreditBalanceProps {
  className?: string;
  showDetails?: boolean;
}

export function CreditBalance({
  className = "",
  showDetails = false,
}: CreditBalanceProps) {
  const { t } = useTranslation(['chat', 'common']);
  const { data: profile, isLoading, isError } = useUserProfile();
  const [isBlurred, setIsBlurred] = useState(false);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={`px-3 py-3 rounded-xl bg-white/60 border border-gray-200/50 animate-pulse ${className}`}
      >
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 bg-gray-200 rounded-lg"></div>
          <div className="flex-1">
            <div className="h-3 bg-gray-200 rounded w-20 mb-1"></div>
            <div className="h-4 bg-gray-200 rounded w-16"></div>
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (isError || !profile) {
    return (
      <div
        className={`px-3 py-3 rounded-xl bg-red-50/80 border border-red-200/50 ${className}`}
      >
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-red-100 text-red-600">
            <AlertCircle size={18} />
          </div>
          <div className="flex-1">
            <p className="text-xs text-red-600 font-medium">
              {t('chat:credits.failedToLoad')}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Determine color based on balance
  const getBalanceColor = (balance: number) => {
    if (balance > 500) return "text-green-600";
    if (balance > 100) return "text-blue-600";
    if (balance > 10) return "text-orange-600";
    return "text-red-600";
  };

  const getGradientColor = (balance: number) => {
    if (balance > 500) return "from-green-500 to-emerald-500";
    if (balance > 100) return "from-blue-500 to-indigo-500";
    if (balance > 10) return "from-orange-500 to-amber-500";
    return "from-red-500 to-rose-500";
  };

  const balanceColor = getBalanceColor(profile.credits);
  const gradientColor = getGradientColor(profile.credits);

  return (
    <div
      className={`px-3 py-3 rounded-xl bg-white/60 hover:bg-white/80 transition-all duration-200 ${className}`}
    >
      <div className="flex items-center gap-3">
        {/* Icon */}
        <div
          className={`flex-shrink-0 w-9 h-9 rounded-lg flex items-center justify-center bg-gradient-to-br ${gradientColor} text-white shadow-md`}
        >
          <Coins size={18} />
        </div>

        {/* Balance */}
        <div className="flex-1 min-w-0">
          <p className="text-xs text-gray-600 font-medium mb-0.5">
            {t('chat:credits.balance')}
          </p>
          <div className="flex items-center gap-2">
            <p className={`text-lg font-bold ${balanceColor} ${isBlurred ? 'blur-sm select-none' : ''} transition-all`}>
              {profile.credits.toFixed(1)}
            </p>
            <button
              onClick={() => setIsBlurred(!isBlurred)}
              className="text-gray-400 hover:text-gray-600 transition-colors flex-shrink-0"
              title={isBlurred ? t('chat:credits.showBalance') : t('chat:credits.hideBalance')}
            >
              {isBlurred ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>

          {/* Details (optional) */}
          {showDetails && (
            <div className={`mt-2 pt-2 border-t border-gray-200/50 space-y-1 ${isBlurred ? 'blur-sm select-none' : ''} transition-all`}>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600 flex items-center gap-1">
                  <TrendingUp size={12} />
                  {t('chat:credits.totalUsed')}
                </span>
                <span className="font-semibold text-gray-800">
                  {profile.total_tokens_used.toLocaleString()} {t('chat:credits.tokens')}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-600">{t('chat:credits.totalSpent')}</span>
                <span className="font-semibold text-gray-800">
                  {profile.total_credits_spent.toFixed(1)} {t('chat:credits.creditsUnit')}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Low balance warning */}
      {profile.credits < 10 && (
        <div className="mt-2 px-2 py-1.5 bg-red-50 border border-red-200/50 rounded-lg">
          <p className="text-xs text-red-600 font-medium flex items-center gap-1">
            <AlertCircle size={12} />
            {t('chat:credits.lowBalanceWarning')}
          </p>
        </div>
      )}
    </div>
  );
}
