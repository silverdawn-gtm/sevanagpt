"use client";

import { useLanguage } from "@/context/LanguageContext";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useLanguage();

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center max-w-md">
        <div className="text-6xl mb-4">{t("error.title")}</div>
        <p className="text-gray-600 mb-6">
          {error.message || t("error.default_message")}
        </p>
        <button
          onClick={reset}
          className="px-6 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700"
        >
          {t("error.try_again")}
        </button>
      </div>
    </div>
  );
}
