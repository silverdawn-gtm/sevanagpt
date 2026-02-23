"use client";

import { useState, useCallback, useEffect } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { getSpeechLang, isSpeechSynthesisSupported } from "@/lib/speechLanguageMap";

interface ReadAloudButtonProps {
  text: string;
}

export default function ReadAloudButton({ text }: ReadAloudButtonProps) {
  const { language, t } = useLanguage();
  const [speaking, setSpeaking] = useState(false);

  const speechLang = getSpeechLang(language);
  const supported = isSpeechSynthesisSupported() && speechLang !== null;

  // Cancel speech on unmount
  useEffect(() => {
    return () => {
      window.speechSynthesis?.cancel();
    };
  }, []);

  const handleClick = useCallback(() => {
    if (!supported || !speechLang) return;

    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text.slice(0, 500));
    utterance.lang = speechLang;

    // Try to find a matching voice
    const voices = window.speechSynthesis.getVoices();
    const match = voices.find((v) => v.lang === speechLang) ||
      voices.find((v) => v.lang.startsWith(speechLang.split("-")[0]));
    if (match) utterance.voice = match;

    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
    setSpeaking(true);
  }, [supported, speechLang, speaking, text]);

  if (!supported) return null;

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200 hover:bg-emerald-100 transition-colors"
      title="Read aloud"
    >
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        {speaking ? (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        ) : (
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z" />
        )}
      </svg>
      {speaking ? t("scheme_detail.stop") : t("scheme_detail.listen")}
    </button>
  );
}
