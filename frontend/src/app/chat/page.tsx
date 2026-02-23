"use client";

import { useChat } from "@/hooks/useChat";
import ChatWindow from "@/components/chat/ChatWindow";
import ChatInput from "@/components/chat/ChatInput";
import { useLanguage } from "@/context/LanguageContext";

export default function ChatPage() {
  const { messages, loading, sendMessage, reset } = useChat();
  const { language, t } = useLanguage();

  const lastAssistant = messages.filter((m) => m.role === "assistant").at(-1);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col" style={{ minHeight: "calc(100vh - 12rem)" }}>
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold text-gray-900">{t("chat.title")}</h1>
        {messages.length > 0 && (
          <button
            onClick={reset}
            className="px-3 py-1.5 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            {t("chat.new_chat")}
          </button>
        )}
      </div>
      <p className="text-gray-500 mb-6">{t("chat.subtitle")}</p>

      <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
        <ChatWindow messages={messages} loading={loading} />
        <ChatInput
          onSend={sendMessage}
          disabled={loading}
          suggestions={messages.length > 0 && !loading && lastAssistant?.suggestions?.length ? lastAssistant.suggestions : undefined}
          language={language}
        />
      </div>
    </div>
  );
}
