"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getMinistries } from "@/lib/api";
import type { Ministry } from "@/lib/types";
import { useLanguage } from "@/context/LanguageContext";

export default function MinistriesPage() {
  const { language, t } = useLanguage();
  const [ministries, setMinistries] = useState<Ministry[]>([]);

  useEffect(() => {
    getMinistries(language).then(setMinistries).catch(() => {});
  }, [language]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">{t("browse.by_ministry")}</h1>
      <p className="text-gray-600 mb-8">{t("browse.ministry_subtitle")}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {ministries.map((ministry) => (
          <Link
            key={ministry.id}
            href={`/ministries/${ministry.slug}`}
            className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-emerald-300 transition-all"
          >
            <span className="font-medium text-gray-900">{ministry.name}</span>
            <span className="text-sm text-gray-500 shrink-0 ml-2">{ministry.scheme_count} {t("browse.schemes")}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
