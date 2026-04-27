import { useState, useMemo, useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useChatManager } from "./chat/useChatManager";
import { useAnalysis } from "./chat/useAnalysis";
import { ChatMessages } from "./chat/ChatMessages";
import { ChatInput } from "./chat/ChatInput";
import { ChatSidebar } from "./chat/ChatSidebar";
import { useChatRestoration } from "../hooks/useChatRestoration";
import { useUIStateSync } from "../hooks/useUIStateSync";
import type { ModelSettings } from "../types/models";
import type { DeepStreamEvent } from "../types/api";
import {
  useDeepAccordionState,
  DeepAgentAccordion,
  mapDeepEventToAction,
} from "./chat/deep";
import { parseBackendMessage, replayDeepEvents } from "../utils/messageParser";

export function EnhancedChatInterface() {
  const { t } = useTranslation(["chat", "common"]);
  const [message, setMessage] = useState("");
  const [currentSymbol, setCurrentSymbol] = useState("");
  const [currentCompanyName, setCurrentCompanyName] = useState("");
  // Chart UI was removed in the rebrand cleanup. These values are retained
  // as inert defaults so that useAnalysis / useChatRestoration / useUIStateSync
  // can keep their existing signatures without dragging stock-chart state
  // into the chat shell.
  const selectedInterval = "1d" as const;
  const selectedDateRange = useMemo(() => ({ start: "", end: "" }), []);
  const setSelectedInterval = useCallback((_: string) => {}, []);
  const setSelectedDateRange = useCallback(
    (_: { start: string; end: string }) => {},
    [],
  );

  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileSidebarVisible, setIsMobileSidebarVisible] = useState(false);

  const [modelSettings, setModelSettings] = useState<ModelSettings>({
    model: "qwen-plus",
    thinking_enabled: false,
    max_tokens: 3000,
    debug_enabled: false,
  });

  const [agentMode, setAgentMode] = useState<"v2" | "v3" | "v4-deep">("v3");

  const { state: deepState, dispatch: deepDispatch } = useDeepAccordionState();

  const handleDeepEvent = useCallback(
    (event: DeepStreamEvent) => {
      const action = mapDeepEventToAction(event);
      if (action) {
        deepDispatch(action);
      }
    },
    [deepDispatch],
  );

  const deepAccordionElement = useMemo(
    () =>
      agentMode === "v4-deep" && deepState.status !== "pending" ? (
        <DeepAgentAccordion state={deepState} dispatch={deepDispatch} />
      ) : undefined,
    [agentMode, deepState, deepDispatch],
  );

  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  const { messages, setMessages, chatId, setChatId } = useChatManager();

  const { restoreChat } = useChatRestoration({
    setMessages,
    setCurrentSymbol,
    setCurrentCompanyName,
    setSelectedInterval,
    setSelectedDateRange,
    setChatId,
  });

  useUIStateSync({
    activeChatId: chatId,
    currentSymbol,
    currentCompanyName,
    selectedInterval,
    selectedDateRange,
  });

  const chatMutation = useAnalysis(
    currentSymbol,
    selectedDateRange,
    setMessages,
    setSelectedDateRange,
    selectedInterval,
    chatId,
    setChatId,
    modelSettings,
    agentMode,
    agentMode === "v4-deep" ? handleDeepEvent : undefined,
  );

  const handleSendMessage = useCallback(() => {
    if (!message.trim()) return;
    if (chatMutation.isPending) {
      console.log("⏭️ Skipping message submit: request already in progress");
      return;
    }
    chatMutation.mutate(message);
    setMessage("");
  }, [message, chatMutation]);

  const isRestoringRef = useRef(false);

  const handleChatSelect = useCallback(
    async (chatId: string) => {
      if (isRestoringRef.current) {
        console.log("Skipping chat select: restoration in progress");
        return;
      }

      isRestoringRef.current = true;
      try {
        deepDispatch({ type: "RESET" });

        const restoredMessages = await restoreChat(chatId);
        setHasMoreMessages(true);

        if (restoredMessages) {
          const hasDeep = replayDeepEvents(
            restoredMessages,
            mapDeepEventToAction,
            deepDispatch as (action: unknown) => void,
          );
          if (hasDeep) setAgentMode("v4-deep");
        }
      } finally {
        isRestoringRef.current = false;
      }
    },
    [restoreChat, deepDispatch],
  );

  const handleNewChat = useCallback(() => {
    setMessages([]);
    setChatId(null);
    setCurrentSymbol("");
    setCurrentCompanyName("");
    setHasMoreMessages(false);
    deepDispatch({ type: "RESET" });
    setAgentMode("v3");
  }, [setMessages, setChatId, deepDispatch]);

  const handleLoadMore = useCallback(async () => {
    if (!chatId || isLoadingMore) return;

    setIsLoadingMore(true);
    const scrollContainer = document.querySelector("[data-chat-scroll]");
    const prevScrollHeight = scrollContainer?.scrollHeight ?? 0;

    try {
      const { chatService } = await import("../services/api");
      const currentOffset = messages.length;
      const chatDetail = await chatService.getChatDetail(
        chatId,
        50,
        currentOffset,
      );

      if (chatDetail.messages.length === 0) {
        setHasMoreMessages(false);
        return;
      }

      const olderMessages = chatDetail.messages.map(parseBackendMessage);

      if (deepState.status === "pending") {
        const hasDeep = replayDeepEvents(
          olderMessages,
          mapDeepEventToAction,
          deepDispatch as (action: unknown) => void,
        );
        if (hasDeep) setAgentMode("v4-deep");
      }

      setMessages((prev) => [...olderMessages, ...prev]);
      setHasMoreMessages(chatDetail.messages.length === 50);

      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (scrollContainer) {
            const newScrollHeight = scrollContainer.scrollHeight;
            scrollContainer.scrollTop += newScrollHeight - prevScrollHeight;
          }
        });
      });
    } catch (error) {
      console.error("❌ Failed to load more messages:", error);
    } finally {
      setIsLoadingMore(false);
    }
  }, [
    chatId,
    messages.length,
    isLoadingMore,
    setMessages,
    deepDispatch,
    deepState.status,
  ]);

  return (
    <div className="bg-white overflow-hidden max-h-screen">
      <div className="mx-auto">
        <div className="relative">
          <div
            className="flex flex-col lg:grid lg:gap-0 h-[calc(100vh-5rem)]"
            style={{
              gridTemplateColumns: `${isSidebarCollapsed ? "48px" : "240px"} minmax(500px, 1fr)`,
            }}
          >
            <div
              className={`${
                isMobileSidebarVisible
                  ? "absolute top-0 left-0 z-20 h-full w-64 bg-white shadow-2xl"
                  : "hidden"
              } lg:block lg:relative lg:z-0 lg:w-auto lg:border-r lg:border-gray-300 lg:h-full lg:overflow-hidden`}
            >
              <ChatSidebar
                activeChatId={chatId}
                onChatSelect={(id) => void handleChatSelect(id)}
                onNewChat={handleNewChat}
                isCollapsed={isSidebarCollapsed}
                onToggleCollapse={() =>
                  setIsSidebarCollapsed(!isSidebarCollapsed)
                }
              />
            </div>

            {isMobileSidebarVisible && (
              <div
                role="button"
                tabIndex={0}
                className="absolute inset-0 bg-black/50 z-10 lg:hidden"
                onClick={() => setIsMobileSidebarVisible(false)}
                onKeyDown={(e) => {
                  if (e.key === "Escape" || e.key === "Enter") {
                    setIsMobileSidebarVisible(false);
                  }
                }}
                aria-label="Close sidebar"
              />
            )}

            <div className="flex flex-col h-full w-full lg:w-auto lg:min-w-[500px] relative bg-gray-50 overflow-hidden">
              <div className="flex lg:hidden absolute top-2 left-2 right-2 z-10 gap-2">
                <button
                  onClick={() =>
                    setIsMobileSidebarVisible(!isMobileSidebarVisible)
                  }
                  className="px-3 py-1.5 bg-white/90 backdrop-blur-sm border border-gray-200 rounded-lg shadow-sm text-xs font-medium text-gray-700 hover:bg-gray-50"
                >
                  {isMobileSidebarVisible
                    ? t("chat:mobile.hideSidebar")
                    : t("chat:mobile.showChats")}
                </button>
              </div>

              <div className="pt-12 lg:pt-0 flex flex-col h-full">
                <ChatMessages
                  messages={messages}
                  isAnalysisPending={chatMutation.isPending}
                  chatId={chatId}
                  onLoadMore={handleLoadMore}
                  hasMore={hasMoreMessages}
                  isLoadingMore={isLoadingMore}
                  deepAccordion={deepAccordionElement}
                />

                <div className="flex-shrink-0 px-4 py-2 border-t border-gray-100 bg-gray-50/50">
                  <div className="flex items-center gap-3 text-sm">
                    <span className="text-gray-600 font-medium">
                      {t("chat:mode.label")}:
                    </span>
                    <button
                      onClick={() => setAgentMode("v3")}
                      disabled={!!chatId}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                        agentMode === "v3"
                          ? "bg-gradient-to-r from-blue-500 to-indigo-500 text-white shadow-md"
                          : "bg-white text-gray-700 hover:bg-gray-100"
                      } ${
                        chatId
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"
                      }`}
                      title={
                        chatId
                          ? t("chat:mode.locked")
                          : t("chat:mode.agentDescription")
                      }
                    >
                      🤖 {t("chat:mode.agent")}
                    </button>
                    <button
                      onClick={() => setAgentMode("v2")}
                      disabled={!!chatId}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                        agentMode === "v2"
                          ? "bg-gradient-to-r from-purple-500 to-pink-500 text-white shadow-md"
                          : "bg-white text-gray-700 hover:bg-gray-100"
                      } ${
                        chatId
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"
                      }`}
                      title={
                        chatId
                          ? t("chat:mode.locked")
                          : t("chat:mode.copilotDescription")
                      }
                    >
                      👤 {t("chat:mode.copilot")}
                    </button>
                    <button
                      onClick={() => setAgentMode("v4-deep")}
                      disabled={!!chatId}
                      className={`px-3 py-1.5 rounded-lg font-medium transition-all ${
                        agentMode === "v4-deep"
                          ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-md"
                          : "bg-white text-gray-700 hover:bg-gray-100"
                      } ${
                        chatId
                          ? "opacity-50 cursor-not-allowed"
                          : "cursor-pointer"
                      }`}
                      title={
                        chatId
                          ? t("chat:mode.locked")
                          : t("chat:mode.deepDescription")
                      }
                    >
                      🔬 {t("chat:mode.deep")}
                    </button>
                    {chatId && (
                      <span className="ml-auto text-xs text-gray-500 italic">
                        {t("chat:mode.locked")}
                      </span>
                    )}
                  </div>
                </div>

                <ChatInput
                  message={message}
                  setMessage={setMessage}
                  onSendMessage={handleSendMessage}
                  isPending={chatMutation.isPending}
                  currentSymbol={currentSymbol}
                  messages={messages}
                  modelSettings={modelSettings}
                  onModelSettingsChange={setModelSettings}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
