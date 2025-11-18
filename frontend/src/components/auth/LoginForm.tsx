/**
 * Login form component for username/password authentication
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";

interface LoginFormProps {
  onSubmit: (username: string, password: string) => Promise<void>;
  onSwitchToRegister: () => void;
  onSwitchToForgotPassword: () => void;
  loading: boolean;
  error: string;
}

export function LoginForm({
  onSubmit,
  onSwitchToRegister,
  onSwitchToForgotPassword,
  loading,
  error,
}: LoginFormProps) {
  const { t } = useTranslation(["auth", "validation", "common"]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await onSubmit(username, password);
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">
          {t("auth:login.subtitle")}
        </h2>
        <p className="text-gray-600">{t("auth:login.signInToAccount")}</p>
      </div>

      <div>
        <label
          htmlFor="login-username"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          {t("auth:login.username")}
        </label>
        <input
          id="login-username"
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder={t("auth:login.usernamePlaceholder")}
          required
          className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
        />
      </div>

      <div>
        <label
          htmlFor="login-password"
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          {t("auth:login.password")}
        </label>
        <input
          id="login-password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
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
        {loading ? t("auth:login.submitting") : t("auth:login.submit")}
      </button>

      <div className="text-center space-y-2">
        <button
          type="button"
          onClick={onSwitchToForgotPassword}
          className="text-sm text-gray-600 hover:text-gray-900"
        >
          {t("auth:login.forgotPassword")}
        </button>
        <div>
          <button
            type="button"
            onClick={onSwitchToRegister}
            className="text-blue-600 hover:text-blue-800 font-medium text-sm"
          >
            {t("auth:login.register")} &rarr;
          </button>
        </div>
      </div>
    </form>
  );
}
