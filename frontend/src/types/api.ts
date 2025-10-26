export interface HealthResponse {
  status: "ok" | "degraded" | "error";
  environment: string;
  version: string;
  timestamp: string;
  kubernetes?: {
    running_in_kubernetes: boolean;
    pod_name?: string;
    node_name?: string;
    namespace?: string;
    node_pool?: string;
    resources?: {
      requests: {
        cpu: string;
        memory: string;
      };
      limits: {
        cpu: string;
        memory: string;
      };
    };
  };
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
    langfuse_enabled: boolean;
    database_name: string;
  };
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  chart_url?: string;
  analysis_data?: Record<string, unknown>;
  _id?: string | number; // Optional ID for frontend tracking
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

// ===== Chat Types =====

export interface UIState {
  current_symbol?: string | null;
  current_interval?: string;
  current_date_range?: {
    start?: string | null;
    end?: string | null;
  };
  active_overlays?: Record<string, Record<string, unknown>>;
}

export interface Chat {
  chat_id: string;
  user_id: string;
  title: string;
  is_archived: boolean;
  ui_state?: UIState;
  last_message_preview?: string | null;
  created_at: string;
  updated_at: string;
  last_message_at?: string | null;
}

export interface ChatListResponse {
  chats: Chat[];
  total: number;
  page: number;
  page_size: number;
}

export interface Message {
  message_id: string;
  chat_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  source:
    | "user"
    | "llm"
    | "fibonacci"
    | "stochastic"
    | "macro"
    | "fundamentals";
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface ChatDetailResponse {
  chat: Chat;
  messages: Message[];
}

export interface UpdateUIStateRequest {
  ui_state: UIState;
}

// ===== Stream Event Types =====

export type StreamEvent =
  | {
      type: "chat_created";
      chat_id: string;
    }
  | {
      type: "chunk";
      content: string;
    }
  | {
      type: "title_generated";
      title: string;
    }
  | {
      type: "done";
      chat_id: string;
      message_count?: number;
    }
  | {
      type: "error";
      error?: string;
    };
