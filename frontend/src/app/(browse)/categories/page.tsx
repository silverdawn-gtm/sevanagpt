"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCategories } from "@/lib/api";
import type { Category } from "@/lib/types";
import { CATEGORY_ICONS } from "@/lib/constants";
import { useLanguage } from "@/context/LanguageContext";

export default function CategoriesPage() {
  const { language, t } = useLanguage();
  const [categories, setCategories] = useState<Category[]>([]);

  useEffect(() => {
    getCategories(language).then(setCategories).catch(() => {});
  }, [language]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">{t("browse.by_category")}</h1>
      <p className="text-gray-600 mb-8">{t("browse.category_subtitle")}</p>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
        {categories.map((cat) => (
          <Link
            key={cat.id}
            href={`/categories/${cat.slug}`}
            className="flex items-center gap-4 p-5 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-emerald-300 transition-all"
          >
            <span className="text-4xl">{CATEGORY_ICONS[cat.icon || ""] || "📋"}</span>
            <div>
              <div className="font-semibold text-gray-900">{cat.name}</div>
              <div className="text-sm text-gray-500">{cat.scheme_count} {t("browse.schemes")}</div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
