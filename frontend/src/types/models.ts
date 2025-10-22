/**
 * LLM Model Configuration Types
 * Matches backend model_config.py structure
 */

export interface ModelPricing {
  input_cost_per_1k: number; // CNY per 1000 tokens
  output_cost_per_1k: number; // CNY per 1000 tokens
  thinking_output_multiplier: number; // Cost multiplier for thinking mode (e.g., 4.0)
}

export interface ModelInfo {
  model_id: string; // Model identifier (e.g., 'qwen-plus')
  display_name: string; // Human-readable name
  provider: string; // Provider name (e.g., 'alibaba')
  pricing: ModelPricing;
  max_tokens: number; // Maximum tokens allowed
  default_max_tokens: number; // Recommended default
  supports_thinking: boolean; // Whether thinking mode is supported
  description: string; // Description for UI (e.g., "Balanced - Best value")
  order: number; // Display order (1=highest priority)
}

export interface ModelsListResponse {
  models: ModelInfo[];
  default_model: string; // Default model ID
}

export interface ModelSettings {
  model: string; // Selected model ID
  thinking_enabled: boolean;
  max_tokens: number;
  debug_enabled: boolean; // Enable debug logging (shows full LLM prompts in backend logs)
}
