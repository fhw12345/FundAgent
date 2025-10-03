import axios from 'axios'
import type { HealthResponse, ChatRequest, ChatResponse } from '../types/api'

// Configure axios with base URL
// In production, use empty string for relative URLs (nginx proxy)
// In development, use localhost
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : (import.meta.env.MODE === 'production' ? '' : 'http://localhost:8000'),
  timeout: 30000, // 30 seconds for analysis requests
  headers: {
    'Content-Type': 'application/json',
  },
})

// Export the configured axios instance for use in other services
export const apiClient = api

// Request interceptor for authentication (future)
api.interceptors.request.use(
  (config) => {
    // Add auth token when available
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // Handle authentication errors
      localStorage.removeItem('auth_token')
      // Could redirect to login page
    }
    return Promise.reject(error)
  }
)

// Health service
export const healthService = {
  async getHealth(): Promise<HealthResponse> {
    const response = await api.get<HealthResponse>('/api/health')
    return response.data
  },

  async getMongoHealth(): Promise<{ connected: boolean; [key: string]: unknown }> {
    const response = await api.get('/api/health/mongodb')
    return response.data
  },

  async getRedisHealth(): Promise<{ connected: boolean; [key: string]: unknown }> {
    const response = await api.get('/api/health/redis')
    return response.data
  },

  async getReadiness(): Promise<{ ready: boolean; [key: string]: unknown }> {
    const response = await api.get('/api/health/ready')
    return response.data
  },

  async getLiveness(): Promise<{ alive: boolean; [key: string]: unknown }> {
    const response = await api.get('/api/health/live')
    return response.data
  },
}

// Chat service
export const chatService = {
  async sendMessage(message: string, sessionId?: string): Promise<ChatResponse> {
    const request: ChatRequest = {
      message,
      session_id: sessionId,
    }

    // For now, return mock response since chat endpoint isn't implemented yet
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          response: `Mock response for: "${message}". The chat endpoint will be implemented when we add the LangChain agent integration.`,
          session_id: sessionId || `session_${Date.now()}`,
          requires_approval: false,
        })
      }, 1500) // Simulate API delay
    })

    // Future implementation:
    // const response = await api.post<ChatResponse>('/api/chat', request)
    // return response.data
  },

  async approveAnalysis(sessionId: string, approval: boolean): Promise<ChatResponse> {
    const response = await api.post<ChatResponse>(`/api/approve/${sessionId}`, {
      approval,
    })
    return response.data
  },
}

// Analysis service (future implementation)
export const analysisService = {
  async getFibonacci(symbol: string, timeframe: string = '6mo') {
    const response = await api.post('/api/analysis/fibonacci', {
      symbol,
      timeframe,
    })
    return response.data
  },

  async getMacroSentiment() {
    const response = await api.get('/api/analysis/macro')
    return response.data
  },

  async getMarketStructure(symbol: string, timeframe: string = '6mo') {
    const response = await api.post('/api/analysis/market-structure', {
      symbol,
      timeframe,
    })
    return response.data
  },

  async getFundamentals(symbol: string) {
    const response = await api.get(`/api/analysis/fundamentals/${symbol}`)
    return response.data
  },
}