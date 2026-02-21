"use client";

import { useState } from "react";
import { useVoiceRecorder } from "@/hooks/useVoiceRecorder";
import { useLanguage } from "@/context/LanguageContext";
import clsx from "clsx";

interface VoiceResponse {
  transcript: string;
  reply: string;
  reply_audio_base64: string | null;
  schemes: unknown[];
  suggestions: { text: string }[];
  session_id: string;
}

interface VoiceButtonProps {
  onVoiceResponse: (response: VoiceResponse) => void;
  disabled?: boolean;
  sessionId: string;
}

export default function VoiceButton({ onVoiceResponse, disabled, sessionId }: VoiceButtonProps) {
  const { isRecording, startRecording, stopRecording } = useVoiceRecorder();
  const { language, t } = useLanguage();
  const [processing, setProcessing] = useState(false);

  async function handleClick() {
    if (processing) return;

    if (isRecording) {
      const blob = await stopRecording();
      if (!blob) return;

      setProcessing(true);

      const formData = new FormData();
      formData.append("audio", blob, "recording.webm");
      formData.append("language", language);
      formData.append("session_id", sessionId);

      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
        const res = await fetch(`${API_BASE}/chat/voice`, {
          method: "POST",
          body: formData,
        });
        if (res.ok) {
          const data: VoiceResponse = await res.json();
          onVoiceResponse(data);
        }
      } catch (error) {
        console.error("Voice processing failed:", error);
      } finally {
        setProcessing(false);
      }
    } else {
      await startRecording();
    }
  }

  return (
    <button
      onClick={handleClick}
      disabled={disabled || processing}
      className={clsx(
        "p-2 rounded-lg transition-colors",
        isRecording
          ? "bg-red-500 text-white animate-pulse"
          : processing
            ? "bg-yellow-100 text-yellow-600"
            : "bg-gray-100 text-gray-600 hover:bg-gray-200",
        (disabled || processing) && "opacity-50 cursor-not-allowed"
      )}
      title={
        processing
          ? t("chat.processing")
          : isRecording
            ? t("chat.stop_recording")
            : t("chat.start_voice")
      }
    >
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {processing ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        ) : isRecording ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        )}
      </svg>
    </button>
  );
}
