"use client";

import { createContext, useContext, useState, useEffect, ReactNode } from "react";

const LANGUAGES = [
  { code: "en", name: "English", native: "English" },
  { code: "hi", name: "Hindi", native: "हिन्दी" },
  { code: "bn", name: "Bengali", native: "বাংলা" },
  { code: "ta", name: "Tamil", native: "தமிழ்" },
  { code: "te", name: "Telugu", native: "తెలుగు" },
  { code: "mr", name: "Marathi", native: "मराठी" },
  { code: "gu", name: "Gujarati", native: "ગુજરાતી" },
  { code: "kn", name: "Kannada", native: "ಕನ್ನಡ" },
  { code: "ml", name: "Malayalam", native: "മലയാളം" },
  { code: "pa", name: "Punjabi", native: "ਪੰਜਾਬੀ" },
  { code: "or", name: "Odia", native: "ଓଡ଼ିଆ" },
  { code: "ur", name: "Urdu", native: "اردو" },
];

interface LanguageContextType {
  language: string;
  setLanguage: (lang: string) => void;
  languages: typeof LANGUAGES;
  t: (key: string) => string;
  translations: Record<string, any>;
}

const LanguageContext = createContext<LanguageContextType>({
  language: "en",
  setLanguage: () => {},
  languages: LANGUAGES,
  t: (key) => key,
  translations: {},
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState("en");
  const [translations, setTranslations] = useState<Record<string, any>>({});

  useEffect(() => {
    // Load translations
    fetch(`/locales/${language}/common.json`)
      .then((res) => res.json())
      .then(setTranslations)
      .catch(() => setTranslations({}));
  }, [language]);

  function setLanguage(lang: string) {
    setLanguageState(lang);
    if (typeof window !== "undefined") {
      localStorage.setItem("myscheme_lang", lang);
      document.documentElement.lang = lang;
    }
  }

  function t(key: string): string {
    const keys = key.split(".");
    let value: any = translations;
    for (const k of keys) {
      value = value?.[k];
    }
    return typeof value === "string" ? value : key;
  }

  useEffect(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("myscheme_lang");
      if (saved && LANGUAGES.some((l) => l.code === saved)) {
        setLanguageState(saved);
      }
    }
  }, []);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, languages: LANGUAGES, t, translations }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
