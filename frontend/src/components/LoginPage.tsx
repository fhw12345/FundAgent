/**
 * Login page with username/password and email registration.
 * New users: Email → Code → Username + Password (register)
 * Existing users: Username + Password (login)
 */

import { useState } from "react";
import {
  sendVerificationCode,
  registerUser,
  loginWithPassword,
  resetPassword,
  authStorage,
} from "../services/authService";

interface LoginPageProps {
  onLoginSuccess: () => void;
}

type Mode = "login" | "register" | "forgot-password";
type RegisterStep = "email" | "code" | "credentials";
type ForgotPasswordStep = "email" | "code" | "new-password";

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [mode, setMode] = useState<Mode>("login");

  // Login state
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Registration state
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [registerStep, setRegisterStep] = useState<RegisterStep>("email");

  // Forgot password state
  const [forgotEmail, setForgotEmail] = useState("");
  const [forgotCode, setForgotCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [forgotPasswordStep, setForgotPasswordStep] =
    useState<ForgotPasswordStep>("email");

  // Common state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // === Login handlers ===
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await loginWithPassword(loginUsername, loginPassword);

      // Store token and user
      authStorage.setToken(response.access_token);
      authStorage.setUser(response.user);

      // Redirect to platform
      onLoginSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  // === Registration handlers ===
  const handleSendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await sendVerificationCode(email);
      setRegisterStep("code");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send code");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e: React.FormEvent) => {
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

      // Store token and user
      authStorage.setToken(response.access_token);
      authStorage.setUser(response.user);

      // Redirect to platform
      onLoginSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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

  const switchToRegister = () => {
    setMode("register");
    setRegisterStep("email");
    setError("");
  };

  const switchToLogin = () => {
    setMode("login");
    setError("");
  };

  const switchToForgotPassword = () => {
    setMode("forgot-password");
    setForgotPasswordStep("email");
    setError("");
  };

  // === Forgot Password handlers ===
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

  const handleForgotPasswordVerifyCode = async (e: React.FormEvent) => {
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

      // Store token and user
      authStorage.setToken(response.access_token);
      authStorage.setUser(response.user);

      // Redirect to platform
      onLoginSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password reset failed");
    } finally {
      setLoading(false);
    }
  };

  const handleBackToLoginFromForgot = () => {
    setMode("login");
    setForgotPasswordStep("email");
    setForgotEmail("");
    setForgotCode("");
    setNewPassword("");
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
            AI-Powered Financial Intelligence Platform
          </p>
        </div>

        {/* Login/Register/Forgot Password card */}
        <div className="bg-white/80 backdrop-blur-xl rounded-2xl shadow-xl border border-gray-200/50 p-8">
          {mode === "login" && (
            // ===== LOGIN FORM =====
            <form onSubmit={handleLogin} className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-2">
                  Welcome back
                </h2>
                <p className="text-gray-600">Sign in to your account</p>
              </div>

              <div>
                <label
                  htmlFor="login-username"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Username
                </label>
                <input
                  id="login-username"
                  type="text"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  placeholder="your_username"
                  required
                  className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                />
              </div>

              <div>
                <label
                  htmlFor="login-password"
                  className="block text-sm font-medium text-gray-700 mb-2"
                >
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
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
                {loading ? "Signing in..." : "Sign In"}
              </button>

              <div className="text-center space-y-2">
                <button
                  type="button"
                  onClick={switchToForgotPassword}
                  className="text-sm text-gray-600 hover:text-gray-900"
                >
                  Forgot password?
                </button>
                <div>
                  <button
                    type="button"
                    onClick={switchToRegister}
                    className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                  >
                    Don't have an account? Register →
                  </button>
                </div>
              </div>
            </form>
          )}

          {mode === "register" && (
            // ===== REGISTRATION FLOW =====
            <>
              {registerStep === "email" && (
                <form onSubmit={handleSendCode} className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">
                      Create account
                    </h2>
                    <p className="text-gray-600">
                      Enter your email to get started
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="email"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Email address
                    </label>
                    <input
                      id="email"
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
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

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {loading ? "Sending..." : "Send Verification Code"}
                  </button>

                  <div className="text-center">
                    <button
                      type="button"
                      onClick={switchToLogin}
                      className="text-blue-600 hover:text-blue-800 font-medium text-sm"
                    >
                      ← Back to login
                    </button>
                  </div>
                </form>
              )}

              {registerStep === "code" && (
                <form onSubmit={handleVerifyCode} className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">
                      Enter code
                    </h2>
                    <p className="text-gray-600">
                      We sent a verification code to{" "}
                      <span className="font-semibold">{email}</span>
                    </p>
                  </div>

                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                    <p className="text-sm text-blue-800 font-medium mb-1">
                      📧 Check your email
                    </p>
                    <p className="text-xs text-blue-700">
                      We've sent a 6-digit verification code to your inbox.
                      Please check your email and enter the code below.
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="code"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Verification code
                    </label>
                    <input
                      id="code"
                      type="text"
                      value={code}
                      onChange={(e) =>
                        setCode(e.target.value.replace(/\D/g, "").slice(0, 6))
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
                      disabled={code.length !== 6}
                      className="w-full bg-gradient-to-r from-blue-500 to-indigo-500 text-white font-semibold py-3 px-4 rounded-xl hover:shadow-lg hover:shadow-blue-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      Continue →
                    </button>

                    <button
                      type="button"
                      onClick={handleBackToEmail}
                      className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
                    >
                      ← Back to email
                    </button>
                  </div>
                </form>
              )}

              {registerStep === "credentials" && (
                <form onSubmit={handleRegister} className="space-y-6">
                  <div>
                    <h2 className="text-2xl font-bold text-gray-900 mb-2">
                      Create credentials
                    </h2>
                    <p className="text-gray-600">
                      Choose a username and password
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="username"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Username
                    </label>
                    <input
                      id="username"
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="your_username"
                      required
                      minLength={3}
                      maxLength={20}
                      className="w-full px-4 py-3 rounded-xl border border-gray-300 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      3-20 characters
                    </p>
                  </div>

                  <div>
                    <label
                      htmlFor="password"
                      className="block text-sm font-medium text-gray-700 mb-2"
                    >
                      Password
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
                      Minimum 8 characters
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
                      {loading ? "Creating account..." : "Create Account"}
                    </button>

                    <button
                      type="button"
                      onClick={handleBackToCode}
                      className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
                    >
                      ← Back
                    </button>
                  </div>
                </form>
              )}
            </>
          )}

          {mode === "forgot-password" && (
            // ===== FORGOT PASSWORD FLOW =====
            <>
              {forgotPasswordStep === "email" && (
                <form
                  onSubmit={handleForgotPasswordSendCode}
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
                      onClick={handleBackToLoginFromForgot}
                      className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
                    >
                      ← Back to login
                    </button>
                  </div>
                </form>
              )}

              {forgotPasswordStep === "code" && (
                <form
                  onSubmit={handleForgotPasswordVerifyCode}
                  className="space-y-6"
                >
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
                      We've sent a 6-digit verification code to your inbox.
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
                        setForgotCode(
                          e.target.value.replace(/\D/g, "").slice(0, 6),
                        )
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
                      onClick={handleBackToLoginFromForgot}
                      className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
                    >
                      ← Back to login
                    </button>
                  </div>
                </form>
              )}

              {forgotPasswordStep === "new-password" && (
                <form onSubmit={handleResetPassword} className="space-y-6">
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
                    <p className="text-xs text-gray-500 mt-1">
                      Minimum 8 characters
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
                      {loading ? "Resetting password..." : "Reset Password"}
                    </button>

                    <button
                      type="button"
                      onClick={handleBackToLoginFromForgot}
                      className="w-full text-gray-600 font-medium py-2 hover:text-gray-900 transition-colors"
                    >
                      ← Back to login
                    </button>
                  </div>
                </form>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          By continuing, you agree to our Terms of Service
        </p>
      </div>
    </div>
  );
}
