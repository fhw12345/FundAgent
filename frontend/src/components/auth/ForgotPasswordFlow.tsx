/**
 * Forgot password flow component with email verification
 * Three steps: email → code → new-password
 */

import { useState } from "react";
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
      setError(err instanceof Error ? err.message : "Failed to send code");
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
        newPassword,
      );

      // Store tokens and user
      authStorage.saveLoginResponse(response);

      // Redirect to platform
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
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
              Reset password
            </h2>
            <p className="text-gray-600">
              Enter your email to receive a verification code
            </p>
          </div>

          <div>
            <label
              htmlFor="forgot-email"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Email address
            </label>
            <input
              id="forgot-email"
              type="email"
              value={forgotEmail}
              onChange={(e) => setForgotEmail(e.target.value)}
              placeholder="your.email@163.com"
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
              {loading ? "Sending..." : "Send Verification Code"}
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              ← Back to login
            </button>
          </div>
        </form>
      )}

      {forgotPasswordStep === "code" && (
        <form onSubmit={handleForgotPasswordVerifyCode} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Enter code
            </h2>
            <p className="text-gray-600">
              We sent a verification code to{" "}
              <span className="font-semibold">{forgotEmail}</span>
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <p className="text-sm text-blue-800 font-medium mb-1">
              📧 Check your email
            </p>
            <p className="text-xs text-blue-700">
              We&apos;ve sent a 6-digit verification code to your inbox.
            </p>
          </div>

          <div>
            <label
              htmlFor="forgot-code"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              Verification code
            </label>
            <input
              id="forgot-code"
              type="text"
              value={forgotCode}
              onChange={(e) =>
                setForgotCode(e.target.value.replace(/\D/g, "").slice(0, 6))
              }
              placeholder="000000"
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
              Continue →
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              ← Back to login
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
              Create new password
            </h2>
            <p className="text-gray-600">
              Choose a new password for your account
            </p>
          </div>

          <div>
            <label
              htmlFor="new-password"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              New password
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
            <p className="text-xs text-gray-500 mt-1">Minimum 8 characters</p>
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
              {loading ? "Resetting password..." : "Reset Password"}
            </button>

            <button
              type="button"
              onClick={onBack}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              ← Back to login
            </button>
          </div>
        </form>
      )}
    </>
  );
}
