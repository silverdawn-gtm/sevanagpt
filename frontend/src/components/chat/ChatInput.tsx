"use client";

import { useState, useRef, useEffect } from "react";
import VoiceButton from "./VoiceButton";
import { useLanguage } from "@/context/LanguageContext";

interface VoiceResponse {
  transcript: string;
  reply: string;
  reply_audio_base64: string | null;
  schemes: unknown[];
  suggestions: { text: string }[];
  session_id: string;
}

interface ChatInputProps {
  onSend: (message: string) => void;
  onVoiceResponse?: (response: VoiceResponse) => void;
  disabled?: boolean;
  suggestions?: { text: string }[];
  sessionId?: string;
}

export default function ChatInput({ onSend, onVoiceResponse, disabled, suggestions, sessionId }: ChatInputProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const { t } = useLanguage();

  useEffect(() => {
    inputRef.current?.focus();
  }, [disabled]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  }

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      {/* Suggestions */}
      {suggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => onSend(s.text)}
              disabled={disabled}
              className="px-3 py-1.5 text-sm bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200 hover:bg-emerald-100 disabled:opacity-50 transition-colors"
            >
              {s.text}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("chat.placeholder")}
          disabled={disabled}
          rows={1}
          className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 disabled:bg-gray-50"
        />
        {sessionId && onVoiceResponse && (
          <VoiceButton
            onVoiceResponse={onVoiceResponse}
            disabled={disabled}
            sessionId={sessionId}
          />
        )}
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </form>
    </div>
  );
}
