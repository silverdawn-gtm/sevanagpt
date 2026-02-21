"use client";

import { useRef, useState } from "react";
import { useLanguage } from "@/context/LanguageContext";

interface AudioPlayerProps {
  audioBase64: string;
  mimeType?: string;
}

export default function AudioPlayer({ audioBase64, mimeType = "audio/wav" }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const { t } = useLanguage();

  function toggle() {
    const el = audioRef.current;
    if (!el) return;

    if (playing) {
      el.pause();
      setPlaying(false);
    } else {
      el.play();
      setPlaying(true);
    }
  }

  function handleEnded() {
    setPlaying(false);
  }

  const src = `data:${mimeType};base64,${audioBase64}`;

  return (
    <div className="flex items-center gap-2 mt-1">
      <audio ref={audioRef} src={src} onEnded={handleEnded} />
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-50 text-emerald-700 rounded-full border border-emerald-200 hover:bg-emerald-100 transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          {playing ? (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          ) : (
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          )}
        </svg>
        {playing ? t("chat.pause") : t("chat.play_reply")}
      </button>
    </div>
  );
}
