export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  environment: string;
  version: string;
  timestamp: string;
  dependencies: {
    mongodb: {
      connected: boolean;
      version?: string;
      database?: string;
      error?: string;
    };
    redis: {
      connected: boolean;
      version?: string;
      memory_usage?: string;
      error?: string;
    };
  };
  configuration: {
    langsmith_enabled: boolean;
    database_name: string;
  };
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  chart_url?: string;
  analysis_data?: Record<string, unknown>;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  session_id: string;
  message_count: number;
  chart_url?: string;
  analysis_data?: Record<string, unknown>;
}

export interface FibonacciData {
  symbol: string;
  timeframe: string;
  trend_direction: "uptrend" | "downtrend";
  swing_high: {
    price: number;
    date: string;
  };
  swing_low: {
    price: number;
    date: string;
  };
  fibonacci_levels: Array<{
    level: number;
    price: number;
    percentage: string;
  }>;
  confidence_score: number;
  analysis_summary: string;
}

export interface MacroData {
  vix_level: number;
  vix_interpretation: string;
  market_sentiment: "fearful" | "neutral" | "greedy";
  major_indices: Record<string, number>;
  sector_performance: Record<string, number>;
  overall_confidence: number;
}

export interface ErrorResponse {
  detail: string;
  error_code?: string;
}
