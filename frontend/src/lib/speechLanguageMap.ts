/**
 * Maps ISO 639 language codes to BCP-47 codes for Web Speech API.
 * Only languages with good Chrome Web Speech API support are included.
 */
const SPEECH_LANG_MAP: Record<string, string> = {
  en: "en-IN",
  hi: "hi-IN",
  bn: "bn-IN",
  ta: "ta-IN",
  te: "te-IN",
  mr: "mr-IN",
  gu: "gu-IN",
  kn: "kn-IN",
  ml: "ml-IN",
  pa: "pa-IN",
  ur: "ur-IN",
};

/** Returns BCP-47 speech code for a given ISO language, or null if unsupported. */
export function getSpeechLang(iso: string): string | null {
  return SPEECH_LANG_MAP[iso] ?? null;
}

/** Checks if the browser supports SpeechRecognition. */
export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  return !!(
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition
  );
}

/** Checks if the browser supports SpeechSynthesis. */
export function isSpeechSynthesisSupported(): boolean {
  if (typeof window === "undefined") return false;
  return !!window.speechSynthesis;
}
