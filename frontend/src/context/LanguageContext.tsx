"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import enTranslations from "../../public/locales/en/common.json";

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
  { code: "as", name: "Assamese", native: "অসমীয়া" },
  { code: "ne", name: "Nepali", native: "नेपाली" },
  { code: "sa", name: "Sanskrit", native: "संस्कृतम्" },
  { code: "sd", name: "Sindhi", native: "سنڌي" },
  { code: "mai", name: "Maithili", native: "मैथिली" },
  { code: "doi", name: "Dogri", native: "डोगरी" },
  { code: "kok", name: "Konkani", native: "कोंकणी" },
  { code: "sat", name: "Santali", native: "ᱥᱟᱱᱛᱟᱲᱤ" },
  { code: "mni", name: "Manipuri", native: "মৈতৈলোন্" },
  { code: "bodo", name: "Bodo", native: "बड़ो" },
  { code: "lus", name: "Mizo", native: "Mizo ṭawng" },
];

interface LanguageContextType {
  language: string;
  setLanguage: (lang: string) => void;
  languages: typeof LANGUAGES;
  t: (key: string) => string;
  translations: Record<string, any>;
  translationsReady: boolean;
}

const LanguageContext = createContext<LanguageContextType>({
  language: "en",
  setLanguage: () => {},
  languages: LANGUAGES,
  t: (key) => key,
  translations: enTranslations,
  translationsReady: true,
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  // Read saved language synchronously during init to avoid flash of English
  const [language, setLanguageState] = useState(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("myscheme_lang");
      if (saved && LANGUAGES.some((l) => l.code === saved)) {
        return saved;
      }
    }
    return "en";
  });
  const [translations, setTranslations] = useState<Record<string, any>>(enTranslations);
  const [translationsReady, setTranslationsReady] = useState(language === "en");

  // Set document lang on mount
  useEffect(() => {
    document.documentElement.lang = language;
  }, [language]);

  // Load translations whenever language changes (skip English — already bundled)
  useEffect(() => {
    if (language === "en") {
      setTranslations(enTranslations);
      setTranslationsReady(true);
      return;
    }
    setTranslationsReady(false);
    fetch(`/locales/${language}/common.json`)
      .then((res) => res.json())
      .then((data) => {
        setTranslations(data);
        setTranslationsReady(true);
      })
      .catch(() => {
        setTranslations(enTranslations);
        setTranslationsReady(true);
      });
  }, [language]);

  const setLanguage = useCallback((lang: string) => {
    setLanguageState(lang);
    localStorage.setItem("myscheme_lang", lang);
    document.documentElement.lang = lang;
  }, []);

  const t = useCallback(
    (key: string): string => {
      const keys = key.split(".");
      let value: any = translations;
      for (const k of keys) {
        value = value?.[k];
      }
      return typeof value === "string" ? value : key;
    },
    [translations]
  );

  return (
    <LanguageContext.Provider value={{ language, setLanguage, languages: LANGUAGES, t, translations, translationsReady }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  return useContext(LanguageContext);
}
