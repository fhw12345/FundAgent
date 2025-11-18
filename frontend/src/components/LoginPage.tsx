/**
 * Login page with username/password and email registration.
 * New users: Email → Code → Username + Password (register)
 * Existing users: Username + Password (login)
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { loginWithPassword, authStorage } from "../services/authService";
import { LoginForm } from "./auth/LoginForm";
import { RegistrationFlow } from "./auth/RegistrationFlow";
import { ForgotPasswordFlow } from "./auth/ForgotPasswordFlow";

interface LoginPageProps {
  onLoginSuccess: () => void;
}

type Mode = "login" | "register" | "forgot-password";

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const { t } = useTranslation(['auth', 'common']);
  const [mode, setMode] = useState<Mode>("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // === Login handler ===
  const handleLogin = async (username: string, password: string) => {
    setError("");
    setLoading(true);

    try {
      const response = await loginWithPassword(username, password);

      // Store tokens and user
      authStorage.saveLoginResponse(response);

      // Redirect to platform
      onLoginSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  // === Mode switching ===
  const switchToRegister = () => {
    setMode("register");
    setError("");
  };

  const switchToLogin = () => {
    setMode("login");
    setError("");
  };

  const switchToForgotPassword = () => {
    setMode("forgot-password");
    setError("");
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 px-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex w-16 h-16 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-500 rounded-3xl items-center justify-center shadow-2xl shadow-blue-500/30 ring-4 ring-white/50 mb-4">
            <span className="text-4xl">📊</span>
          </div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent mb-2">
            KlineMatrix
          </h1>
          <p className="text-gray-600">
            {t('auth:login.tagline')}
          </p>
        </div>

        {/* Login/Register/Forgot Password card */}
        <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 p-8">
          {mode === "login" && (
            <LoginForm
              onSubmit={handleLogin}
              onSwitchToRegister={switchToRegister}
              onSwitchToForgotPassword={switchToForgotPassword}
              loading={loading}
              error={error}
            />
          )}

          {mode === "register" && (
            <RegistrationFlow
              onSuccess={onLoginSuccess}
              onBack={switchToLogin}
            />
          )}

          {mode === "forgot-password" && (
            <ForgotPasswordFlow
              onSuccess={onLoginSuccess}
              onBack={switchToLogin}
            />
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          {t('auth:login.termsAgreement')}
        </p>
      </div>
    </div>
  );
}
