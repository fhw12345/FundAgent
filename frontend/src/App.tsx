import { useState } from 'react'
import { HealthCheck } from './components/HealthCheck'
import { ChatInterface } from './components/ChatInterface'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState<'health' | 'chat'>('health')

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div className="flex items-center">
              <h1 className="text-3xl font-bold text-gray-900">
                Financial Agent
              </h1>
              <span className="ml-2 px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                v0.1.0
              </span>
            </div>
            <nav className="flex space-x-8">
              <button
                onClick={() => setActiveTab('health')}
                className={`px-3 py-2 text-sm font-medium rounded-md ${
                  activeTab === 'health'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Health Status
              </button>
              <button
                onClick={() => setActiveTab('chat')}
                className={`px-3 py-2 text-sm font-medium rounded-md ${
                  activeTab === 'chat'
                    ? 'bg-blue-100 text-blue-700'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                Chat Interface
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          {activeTab === 'health' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  System Health Status
                </h2>
                <p className="text-gray-600 mb-6">
                  Real-time status of backend services and dependencies.
                  This demonstrates the "walking skeleton" - end-to-end connectivity
                  from frontend → FastAPI → MongoDB → Redis.
                </p>
              </div>
              <HealthCheck />
            </div>
          )}

          {activeTab === 'chat' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  Financial Analysis Chat
                </h2>
                <p className="text-gray-600 mb-6">
                  Conversational interface for financial analysis requests.
                  Ask for Fibonacci analysis, market structure, or macro sentiment.
                </p>
              </div>
              <ChatInterface />
            </div>
          )}
        </div>
      </main>

      <footer className="bg-white border-t mt-12">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            Financial Agent Platform - AI-Enhanced Financial Analysis
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App