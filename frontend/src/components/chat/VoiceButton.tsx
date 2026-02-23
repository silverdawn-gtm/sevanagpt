"use client";

import { useEffect } from "react";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";
import { useLanguage } from "@/context/LanguageContext";
import clsx from "clsx";

interface VoiceButtonProps {
  onSend: (text: string) => void;
  language: string;
  disabled?: boolean;
}

export default function VoiceButton({ onSend, language, disabled }: VoiceButtonProps) {
  const { isListening, transcript, interimTranscript, startListening, stopListening, supported } =
    useSpeechRecognition(language);
  const { t } = useLanguage();

  // When recognition ends with a final transcript, send it
  useEffect(() => {
    if (!isListening && transcript) {
      onSend(transcript);
    }
  }, [isListening, transcript, onSend]);

  if (!supported) return null;

  function handleClick() {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  }

  return (
    <div className="relative">
      <button
        onClick={handleClick}
        disabled={disabled}
        className={clsx(
          "p-2 rounded-lg transition-colors",
          isListening
            ? "bg-red-500 text-white animate-pulse"
            : "bg-gray-100 text-gray-600 hover:bg-gray-200",
          disabled && "opacity-50 cursor-not-allowed"
        )}
        title={isListening ? t("chat.stop_recording") : t("chat.start_voice")}
      >
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {isListening ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
            />
          )}
        </svg>
      </button>

      {/* Floating interim transcript bubble */}
      {isListening && interimTranscript && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 w-48 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg whitespace-pre-wrap text-center">
          {interimTranscript}
        </div>
      )}
    </div>
  );
}
