import { useState } from "react";
import { HelpCircle } from "lucide-react";
import { EnhancedChatInterface } from "./components/EnhancedChatInterface";
import HealthPage from "./pages/HealthPage";
import PortfolioDashboard from "./pages/PortfolioDashboard";
import TransactionsPage from "./pages/TransactionsPage";
import FundDetailPage from "./pages/FundDetailPage";
import HelpModal from "./components/HelpModal";

function App() {
  const [activeTab, setActiveTab] = useState<
    "health" | "chat" | "portfolio" | "transactions"
  >("portfolio");
  const [detailFundCode, setDetailFundCode] = useState<string | null>(null);
  const [isHelpModalOpen, setIsHelpModalOpen] = useState(false);

  const navItems: { key: typeof activeTab; label: string }[] = [
    { key: "portfolio", label: "我的持仓" },
    { key: "transactions", label: "交易记录" },
    { key: "chat", label: "AI 对话" },
    { key: "health", label: "系统状态" },
  ];

  // Make navigation function available globally so child components can call it
  // (avoid prop drilling — works fine for personal app)
  if (typeof window !== "undefined") {
    (window as unknown as { openFundDetail: (code: string) => void }).openFundDetail = (code: string) => setDetailFundCode(code);
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-white/70 border-b border-gray-200/50 shadow-sm">
        <div className="mx-auto px-3 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center py-2 gap-2">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="w-9 h-9 sm:w-11 sm:h-11 bg-gradient-to-br from-blue-500 via-indigo-500 to-purple-500 rounded-xl sm:rounded-2xl flex items-center justify-center shadow-lg shadow-blue-500/30 ring-2 ring-white/50">
                <span className="text-xl sm:text-2xl">📊</span>
              </div>
              <div>
                <h1 className="text-lg sm:text-xl font-bold bg-gradient-to-r from-gray-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent tracking-tight">
                  FundAgent
                </h1>
                <span className="text-xs font-medium text-gray-500 hidden sm:inline">
                  AI 基金分析助手
                </span>
              </div>
            </div>

            <nav className="flex flex-wrap items-center gap-1.5 sm:gap-2">
              {navItems.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setActiveTab(item.key)}
                  className={`px-3 sm:px-5 py-1.5 sm:py-2.5 text-xs sm:text-sm font-semibold rounded-lg sm:rounded-xl transition-all duration-200 ${
                    activeTab === item.key
                      ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-lg shadow-blue-500/30"
                      : "text-gray-700 hover:bg-gray-100/80"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 mx-auto w-full">
        {detailFundCode ? (
          <FundDetailPage fundCode={detailFundCode} onBack={() => setDetailFundCode(null)} />
        ) : (
          <>
            {activeTab === "health" && <HealthPage />}
            {activeTab === "chat" && <EnhancedChatInterface />}
            {activeTab === "portfolio" && <PortfolioDashboard />}
            {activeTab === "transactions" && <TransactionsPage />}
          </>
        )}
      </main>

      <footer className="bg-white border-t">
        <div className="mx-auto py-3 px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            FundAgent - AI 基金分析助手
          </p>
        </div>
      </footer>

      <button
        onClick={() => setIsHelpModalOpen(true)}
        className="fixed bottom-6 left-6 w-14 h-14 bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-full shadow-lg shadow-blue-500/30 hover:shadow-xl hover:shadow-blue-500/40 hover:scale-110 transition-all duration-200 flex items-center justify-center z-40 group"
        aria-label="帮助"
      >
        <HelpCircle className="w-7 h-7 group-hover:rotate-12 transition-transform duration-200" />
      </button>

      <HelpModal
        isOpen={isHelpModalOpen}
        onClose={() => setIsHelpModalOpen(false)}
      />
    </div>
  );
}

export default App;
