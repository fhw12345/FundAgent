import { useState } from "react";
import { HealthCheck } from "./components/HealthCheck";
import { EnhancedChatInterface } from "./components/EnhancedChatInterface";
import "./App.css";

function App() {
  const [activeTab, setActiveTab] = useState<"health" | "chat">("health");

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Fashionable glassmorphism header */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/70 border-b border-gray-200/50 shadow-sm">
        <div className="mx-auto px-6 lg:px-8">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 ring-2 ring-white/50">
                <span className="text-2xl">📊</span>
              </div>
              <div>
                <h1 className="text-xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent tracking-tight">
                  Financial Agent
                </h1>
                <span className="text-xs font-medium text-gray-500">
                  AI-Powered Analytics
                </span>
              </div>
            </div>
            <nav className="flex gap-2">
              <button
                onClick={() => setActiveTab("health")}
                className={`px-5 py-2.5 text-sm font-semibold rounded-xl transition-all duration-200 ${
                  activeTab === "health"
                    ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/30"
                    : "text-gray-700 hover:bg-gray-100/80"
                }`}
              >
                Health
              </button>
              <button
                onClick={() => setActiveTab("chat")}
                className={`px-5 py-2.5 text-sm font-semibold rounded-xl transition-all duration-200 ${
                  activeTab === "chat"
                    ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/30"
                    : "text-gray-700 hover:bg-gray-100/80"
                }`}
              >
                Platform
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="mx-auto py-0">
        {activeTab === "health" && (
          <div className="max-w-7xl mx-auto px-6 lg:px-8 py-8">
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  System Health Status
                </h2>
                <p className="text-gray-600 mb-6">
                  Real-time status of backend services and dependencies. This
                  demonstrates the "walking skeleton" - end-to-end connectivity
                  from frontend → FastAPI → MongoDB → Redis.
                </p>
              </div>
              <HealthCheck />
            </div>
          </div>
        )}

        {activeTab === "chat" && <EnhancedChatInterface />}
      </main>

      <footer className="bg-white border-t mt-auto">
        <div className="mx-auto py-4 px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            Financial Agent Platform - AI-Enhanced Financial Analysis
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;
