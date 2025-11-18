/**
 * Registration flow component with email verification
 * Three steps: email → code → credentials
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import {
  sendVerificationCode,
  registerUser,
  authStorage,
} from "../../services/authService";

type RegisterStep = "email" | "code" | "credentials";

interface RegistrationFlowProps {
  onSuccess: () => void;
  onBack: () => void;
}

export function RegistrationFlow({ onSuccess, onBack }: RegistrationFlowProps) {
  const { t } = useTranslation(["auth", "validation", "common"]);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [registerStep, setRegisterStep] = useState<RegisterStep>("email");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await sendVerificationCode(email);
      setRegisterStep("code");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : t("auth:register.failedToSendCode")
      );
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Move to credentials step (don't verify yet, just collect data)
    setRegisterStep("credentials");
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await registerUser(email, code, username, password);

      // Store tokens and user
      authStorage.saveLoginResponse(response);

      // Redirect to platform
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth:register.failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleBackToEmail = () => {
    setRegisterStep("email");
    setCode("");
    setError("");
  };

  const handleBackToCode = () => {
    setRegisterStep("code");
    setUsername("");
    setPassword("");
    setError("");
  };

  return (
    <>
      {registerStep === "email" && (
        <form onSubmit={(e) => void handleSendCode(e)} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:register.title")}
            </h2>
            <p className="text-gray-600">{t("auth:register.enterEmailToStart")}</p>
          </div>

          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:register.email")}
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t("auth:register.emailPlaceholder")}
              required
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? t("auth:register.sendingCode")
              : t("auth:register.sendCode")}
          </button>

          <div className="text-center">
            <button
              type="button"
              onClick={onBack}
              className="text-blue-600 hover:text-blue-800 font-medium text-sm"
            >
              &larr; {t("auth:register.backToLogin")}
            </button>
          </div>
        </form>
      )}

      {registerStep === "code" && (
        <form onSubmit={handleVerifyCode} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:verification.title")}
            </h2>
            <p className="text-gray-600">
              {t("auth:verification.sentTo")}{" "}
              <span className="font-semibold">{email}</span>
            </p>
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <p className="text-sm text-blue-800 font-medium mb-1">
              {t("auth:verification.checkEmail")}
            </p>
            <p className="text-xs text-blue-700">
              {t("auth:verification.checkEmailHint")}
            </p>
          </div>

          <div>
            <label
              htmlFor="code"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:verification.code")}
            </label>
            <input
              id="code"
              type="text"
              value={code}
              onChange={(e) =>
                setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
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
              disabled={code.length !== 6}
              className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {t("auth:verification.continue")} &rarr;
            </button>

            <button
              type="button"
              onClick={handleBackToEmail}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              &larr; {t("auth:verification.backToEmail")}
            </button>
          </div>
        </form>
      )}

      {registerStep === "credentials" && (
        <form onSubmit={(e) => void handleRegister(e)} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              {t("auth:credentials.title")}
            </h2>
            <p className="text-gray-600">{t("auth:credentials.subtitle")}</p>
          </div>

          <div>
            <label
              htmlFor="username"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:register.username")}
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("auth:register.usernamePlaceholder")}
              required
              minLength={3}
              maxLength={20}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <p className="text-xs text-gray-500 mt-1">
              {t("auth:register.usernameHint")}
            </p>
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-gray-700 mb-2"
            >
              {t("auth:register.password")}
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              minLength={8}
              className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
            />
            <p className="text-xs text-gray-500 mt-1">
              {t("auth:register.passwordHint")}
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
              {loading ? t("auth:register.submitting") : t("auth:register.submit")}
            </button>

            <button
              type="button"
              onClick={handleBackToCode}
              className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
            >
              &larr; {t("auth:credentials.back")}
            </button>
          </div>
        </form>
      )}
    </>
  );
}
