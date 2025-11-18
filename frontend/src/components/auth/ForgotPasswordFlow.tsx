/**
 * Forgot password flow component with email verification
 * Three steps: email → code → new-password
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  sendVerificationCode,
  resetPassword,
  authStorage,
} from "../../services/authService";

type ForgotPasswordStep = "email" | "code" | "new-password";

interface ForgotPasswordFlowProps {
  onSuccess: () => void;
  onBack: () => void;
}

export function ForgotPasswordFlow({
  onSuccess,
  onBack,
}: ForgotPasswordFlowProps) {
  const { t } = useTranslation(["auth", "validation", "common"]);
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotCode, setForgotCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [forgotPasswordStep, setForgotPasswordStep] =
    useState<ForgotPasswordStep>("email");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleForgotPasswordSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await sendVerificationCode(forgotEmail);
      setForgotPasswordStep("code");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("auth:forgotPassword.failedToSendCode")
      );
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPasswordVerifyCode = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setForgotPasswordStep("new-password");
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await resetPassword(
        forgotEmail,
        forgotCode,
        newPassword
      );

      // Store tokens and user
      authStorage.saveLoginResponse(response);

      // Redirect to platform
      onSuccess();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("auth:newPassword.failed")
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {forgotPasswordStep === "email" && (
        <form
          onSubmit={(e) => void handleForgotPasswordSendCode(e)}
          className="space-y-6"
        >
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:forgotPassword.title")}
            </h2>
            <p className="text-gray-600">{t("auth:forgotPassword.subtitle")}</p>
          </div>

          <div>
            <label
              htmlFor="forgot-email"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:forgotPassword.email")}
            </label>
            <input
              id="forgot-email"
              type="email"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              placeholder={t("auth:forgotPassword.emailPlaceholder")}
              required
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? t("auth:forgotPassword.submitting")
                : t("auth:forgotPassword.submit")}
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              &larr; {t("auth:forgotPassword.backToLogin")}
            </button>
          </div>
        </form>
      )}

      {forgotPasswordStep === "code" && (
        <form onSubmit={handleForgotPasswordVerifyCode} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:verification.title")}
            </h2>
            <p className="text-gray-600">
              {t("auth:verification.sentTo")}{" "}
              <span className="font-semibold">{forgotEmail}</span>
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <p className="text-sm text-blue-800 font-medium mb-1">
              {t("auth:verification.checkEmail")}
            </p>
            <p className="text-xs text-blue-700">
              {t("auth:verification.checkEmailHintShort")}
            </p>
          </div>

          <div>
            <label
              htmlFor="forgot-code"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:verification.code")}
            </label>
            <input
              id="forgot-code"
              type="text"
              value={forgotCode}
              onChange={(e) =>
                setForgotCode(e.target.value.replace(/\D/g, "").slice(0, 6))
              }
              placeholder={t("auth:verification.codePlaceholder")}
              required
              maxLength={6}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all text-center text-2xl font-mono tracking-widest"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              type="submit"
              disabled={forgotCode.length !== 6}
              className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("auth:verification.continue")} &rarr;
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              &larr; {t("auth:forgotPassword.backToLogin")}
            </button>
          </div>
        </form>
      )}

      {forgotPasswordStep === "new-password" && (
        <form
          onSubmit={(e) => void handleResetPassword(e)}
          className="space-y-6"
        >
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:newPassword.title")}
            </h2>
            <p className="text-gray-600">{t("auth:newPassword.subtitle")}</p>
          </div>

          <div>
            <label
              htmlFor="new-password"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:newPassword.label")}
            </label>
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <p className="text-xs text-gray-500 mt-1">
              {t("auth:newPassword.hint")}
            </p>
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <div className="space-y-3">
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading
                ? t("auth:newPassword.submitting")
                : t("auth:newPassword.submit")}
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              &larr; {t("auth:forgotPassword.backToLogin")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}
