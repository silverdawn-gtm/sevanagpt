"use client";

import { useChat } from "@/hooks/useChat";
import ChatWindow from "./ChatWindow";
import ChatInput from "./ChatInput";
import { useLanguage } from "@/context/LanguageContext";

export default function HomeChat() {
  const { messages, loading, sendMessage } = useChat();
  const { t, language } = useLanguage();

  const lastAssistant = messages.filter((m) => m.role === "assistant").at(-1);
  const suggestions = [
    { text: t("chat.suggestion_education") },
    { text: t("chat.suggestion_farmer") },
    { text: t("chat.suggestion_health") },
    { text: t("chat.suggestion_housing") },
  ];

  return (
    <>
      {messages.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          <div className="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center mb-4">
            <svg className="w-6 h-6 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-900 mb-1">{t("chat.welcome")}</h3>
          <p className="text-sm text-gray-500 mb-5">{t("chat.welcome_sub")}</p>
          <div className="flex flex-wrap gap-2 justify-center">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => sendMessage(s.text)}
                disabled={loading}
                className="px-3 py-1.5 text-xs bg-gray-50 border border-gray-200 rounded-full hover:border-emerald-300 hover:bg-emerald-50 text-gray-600 transition-colors disabled:opacity-50"
              >
                {s.text}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <ChatWindow messages={messages} loading={loading} />
      )}
      <ChatInput
        onSend={sendMessage}
        disabled={loading}
        suggestions={messages.length > 0 && !loading && lastAssistant?.suggestions?.length ? lastAssistant.suggestions : undefined}
        language={language}
      />
    </>
  );
}
