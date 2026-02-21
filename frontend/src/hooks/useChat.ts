"use client";

import { useState, useCallback } from "react";
import { sendChatMessage } from "@/lib/api";
import { useLanguage } from "@/context/LanguageContext";
import type { ChatMessage } from "@/lib/types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`);
  const { language, t } = useLanguage();

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const response = await sendChatMessage({
          message: text,
          session_id: sessionId,
          language,
        });

        const assistantMsg: ChatMessage = {
          role: "assistant",
          content: response.reply,
          schemes: response.schemes,
          suggestions: response.suggestions,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } catch (error) {
        const errorMsg: ChatMessage = {
          role: "assistant",
          content: t("chat.error_message"),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
      }
    },
    [loading, sessionId, language, t]
  );

  const addVoiceResponse = useCallback(
    (transcript: string, reply: string, audioBase64?: string, schemes?: ChatMessage["schemes"], suggestions?: ChatMessage["suggestions"]) => {
      const userMsg: ChatMessage = { role: "user", content: transcript };
      const assistantMsg: ChatMessage = {
        role: "assistant",
        content: reply,
        schemes,
        suggestions,
        audioBase64: audioBase64 || undefined,
      };
      setMessages((prev) => [...prev, userMsg, assistantMsg]);
    },
    []
  );

  const reset = useCallback(() => {
    setMessages([]);
    fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1"}/chat/reset/${sessionId}`, {
      method: "POST",
    }).catch(() => {});
  }, [sessionId]);

  return { messages, loading, setLoading, sendMessage, addVoiceResponse, reset, sessionId };
}
