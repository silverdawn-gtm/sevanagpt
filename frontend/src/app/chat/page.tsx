"use client";

import { useCallback } from "react";
import { useChat } from "@/hooks/useChat";
import ChatWindow from "@/components/chat/ChatWindow";
import ChatInput from "@/components/chat/ChatInput";
import { useLanguage } from "@/context/LanguageContext";
import type { SchemeListItem } from "@/lib/types";

export default function ChatPage() {
  const { messages, loading, setLoading, sendMessage, addVoiceResponse, reset, sessionId } = useChat();
  const { t } = useLanguage();

  const lastAssistant = messages.filter((m) => m.role === "assistant").at(-1);

  const handleVoiceResponse = useCallback(
    (response: {
      transcript: string;
      reply: string;
      reply_audio_base64: string | null;
      schemes: unknown[];
      suggestions: { text: string }[];
    }) => {
      addVoiceResponse(
        response.transcript,
        response.reply,
        response.reply_audio_base64 || undefined,
        response.schemes as SchemeListItem[],
        response.suggestions,
      );
    },
    [addVoiceResponse]
  );

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 flex flex-col" style={{ minHeight: "calc(100vh - 12rem)" }}>
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("chat.title")}</h1>
      <p className="text-gray-500 mb-6">{t("chat.subtitle")}</p>

      <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 overflow-hidden">
        <ChatWindow messages={messages} loading={loading} />
        <ChatInput
          onSend={sendMessage}
          onVoiceResponse={handleVoiceResponse}
          disabled={loading}
          suggestions={messages.length > 0 && !loading && lastAssistant?.suggestions?.length ? lastAssistant.suggestions : undefined}
          sessionId={sessionId}
        />
      </div>
    </div>
  );
}
