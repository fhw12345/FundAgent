/**
 * ChatInput Component
 *
 * Provides a text input field, settings toggle, and send button.
 */

import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { Send, Settings } from "lucide-react";
import { ModelSettings as IModelSettings } from "../../types/models";
import { ModelSettings } from "./ModelSettings";

interface ChatInputProps {
  message: string;
  setMessage: (message: string) => void;
  onSendMessage: () => void;
  isPending: boolean;
  currentSymbol: string | null;
  messages: Array<{ role: string; content: string }>;
  modelSettings: IModelSettings;
  onModelSettingsChange: (settings: IModelSettings) => void;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  message,
  setMessage,
  onSendMessage,
  isPending,
  currentSymbol,
  modelSettings,
  onModelSettingsChange,
}) => {
  const { t } = useTranslation(['chat', 'common']);
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="flex-shrink-0 border-t border-gray-200 px-4 py-3 bg-white">
      {/* Model Settings Panel */}
      {showSettings && (
        <div className="mb-4">
          <ModelSettings
            settings={modelSettings}
            onChange={onModelSettingsChange}
          />
        </div>
      )}

      <div className="flex gap-3">
        <div className="flex-1">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                onSendMessage();
              }
            }}
            placeholder={
              currentSymbol
                ? t('chat:input.placeholderWithSymbol', { symbol: currentSymbol })
                : t('chat:input.placeholderWithoutSymbol')
            }
            className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-shadow"
            disabled={isPending}
          />
        </div>
        {/* Settings Button */}
        <button
          onClick={() => setShowSettings(!showSettings)}
          className="bg-gray-100 text-gray-700 px-4 py-3 rounded-xl hover:bg-gray-200 transition-colors"
          title={t('chat:settings.modelSettings')}
        >
          <Settings className="h-5 w-5" />
        </button>
        <button
          onClick={onSendMessage}
          disabled={!message.trim() || isPending}
          className="bg-gradient-to-r from-blue-500 to-blue-600 text-white px-5 py-3 rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm hover:shadow-md"
          title={t('chat:input.sendTooltip')}
        >
          <Send className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
};
