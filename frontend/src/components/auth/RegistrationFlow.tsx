/**
 * Registration flow component with email verification
 * Three steps: email → code → credentials
 */

import { useState } from "react";
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
      setError(err instanceof Error ? err.message : "Failed to send code");
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

      // Store token and user
      authStorage.setToken(response.access_token);
      authStorage.setUser(response.user);

      // Redirect to platform
      onSuccess();
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

  return (
    <>
      {registerStep === "email" && (
        <form onSubmit={(e) => void handleSendCode(e)} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Create account
            </h2>
            <p className="text-gray-600">Enter your email to get started</p>
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
              onClick={onBack}
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
              We&apos;ve sent a 6-digit verification code to your inbox. Please
              check your email and enter the code below.
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
        <form onSubmit={(e) => void handleRegister(e)} className="space-y-6">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Create credentials
            </h2>
            <p className="text-gray-600">Choose a username and password</p>
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
            <p className="text-xs text-gray-500 mt-1">3-20 characters</p>
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
  );
}
