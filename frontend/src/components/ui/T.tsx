"use client";

import { useLanguage } from "@/context/LanguageContext";

/**
 * Translation component for use in server component JSX.
 * Renders the translated string for the given key.
 */
export default function T({ k }: { k: string }) {
  const { t } = useLanguage();
  return <>{t(k)}</>;
}
