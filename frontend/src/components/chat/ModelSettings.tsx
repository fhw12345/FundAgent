/**
 * Model Settings Component
 * Allows users to select LLM model, thinking mode, and max tokens
 */

import React, { useEffect, useState } from 'react';
import { ModelInfo, ModelSettings as IModelSettings } from '../../types/models';
import { apiClient } from '../../services/api';

interface ModelSettingsProps {
  settings: IModelSettings;
  onChange: (settings: IModelSettings) => void;
}

export const ModelSettings: React.FC<ModelSettingsProps> = ({
  settings,
  onChange,
}) => {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch available models on mount
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await apiClient.get<{ models: ModelInfo[]; default_model: string }>(
          '/api/models'
        );
        setModels(response.data.models);
        setLoading(false);
      } catch (err) {
        console.error('Failed to fetch models:', err);
        setError('Failed to load models');
        setLoading(false);
      }
    };

    fetchModels();
  }, []);

  // Get current model info
  const currentModel = models.find((m) => m.model_id === settings.model);

  // Handle model change
  const handleModelChange = (modelId: string) => {
    const newModel = models.find((m) => m.model_id === modelId);
    onChange({
      ...settings,
      model: modelId,
      // Reset max_tokens to default for new model
      max_tokens: newModel?.default_max_tokens || 3000,
      // Disable thinking if not supported
      thinking_enabled: newModel?.supports_thinking ? settings.thinking_enabled : false,
    });
  };

  // Handle thinking toggle
  const handleThinkingToggle = () => {
    if (currentModel?.supports_thinking) {
      onChange({
        ...settings,
        thinking_enabled: !settings.thinking_enabled,
      });
    }
  };

  // Handle debug toggle
  const handleDebugToggle = () => {
    onChange({
      ...settings,
      debug_enabled: !settings.debug_enabled,
    });
  };

  // Handle max tokens change
  const handleMaxTokensChange = (value: number) => {
    onChange({
      ...settings,
      max_tokens: value,
    });
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-gray-500">
        Loading models...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-500">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4 bg-white rounded-lg shadow-sm border border-gray-200">
      {/* Model Selector */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Model
        </label>
        <select
          value={settings.model}
          onChange={(e) => handleModelChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {models.map((model) => (
            <option key={model.model_id} value={model.model_id}>
              {model.display_name} - {model.description}
            </option>
          ))}
        </select>
        {currentModel && (
          <p className="mt-1 text-xs text-gray-500">
            Input: {(currentModel.pricing.input_cost_per_1k / 0.001).toFixed(1)} credits/1K tokens ·
            Output: {(currentModel.pricing.output_cost_per_1k / 0.001).toFixed(1)} credits/1K tokens
          </p>
        )}
      </div>

      {/* Thinking Mode Toggle */}
      <div>
        <div className="flex items-center justify-between">
          <label
            className={`text-sm font-medium ${
              currentModel?.supports_thinking
                ? 'text-gray-700'
                : 'text-gray-400'
            }`}
          >
            Thinking Mode
          </label>
          <button
            type="button"
            onClick={handleThinkingToggle}
            disabled={!currentModel?.supports_thinking}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              settings.thinking_enabled && currentModel?.supports_thinking
                ? 'bg-blue-600'
                : 'bg-gray-300'
            } ${
              !currentModel?.supports_thinking
                ? 'opacity-50 cursor-not-allowed'
                : 'cursor-pointer'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                settings.thinking_enabled && currentModel?.supports_thinking
                  ? 'translate-x-6'
                  : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        {currentModel?.supports_thinking && (
          <p className="mt-1 text-xs text-gray-500">
            {settings.thinking_enabled
              ? `Enabled (${currentModel.pricing.thinking_output_multiplier}x output cost)`
              : 'Disabled'}
          </p>
        )}
        {!currentModel?.supports_thinking && (
          <p className="mt-1 text-xs text-gray-400">
            Not supported on this model
          </p>
        )}
      </div>

      {/* Debug Mode Toggle */}
      <div>
        <div className="flex items-center justify-between">
          <label className="text-sm font-medium text-gray-700">
            Debug Mode
          </label>
          <button
            type="button"
            onClick={handleDebugToggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              settings.debug_enabled
                ? 'bg-yellow-500'
                : 'bg-gray-300'
            } cursor-pointer`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                settings.debug_enabled
                  ? 'translate-x-6'
                  : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        <p className="mt-1 text-xs text-gray-500">
          {settings.debug_enabled
            ? '🔍 Full LLM prompts logged to backend'
            : 'Disabled - No debug logging'}
        </p>
      </div>

      {/* Max Tokens Slider */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">
            Max Response Tokens
          </label>
          <span className="text-sm text-gray-600">{settings.max_tokens}</span>
        </div>
        <input
          type="range"
          min="500"
          max="3000"
          step="100"
          value={settings.max_tokens}
          onChange={(e) => handleMaxTokensChange(parseInt(e.target.value))}
          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>500</span>
          <span>3000</span>
        </div>
      </div>

      {/* Cost Preview */}
      {currentModel && (
        <div className="pt-3 border-t border-gray-200">
          <p className="text-xs text-gray-600">
            <strong>Estimated cost for {settings.max_tokens} output tokens:</strong>
            <br />
            ~{(
              (settings.max_tokens / 1000) *
              currentModel.pricing.output_cost_per_1k *
              (settings.thinking_enabled ? currentModel.pricing.thinking_output_multiplier : 1) /
              0.001
            ).toFixed(1)} credits
          </p>
        </div>
      )}
    </div>
  );
};
