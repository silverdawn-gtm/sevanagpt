"use client";

import Link from "next/link";
import type { SchemeListItem } from "@/lib/types";
import { useLanguage } from "@/context/LanguageContext";

export default function SchemeCard({ scheme }: { scheme: SchemeListItem }) {
  const { t } = useLanguage();

  return (
    <Link
      href={`/schemes/${scheme.slug}`}
      className="block bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md hover:border-emerald-300 transition-all"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">{scheme.name}</h3>
          {scheme.description && (
            <p className="text-sm text-gray-600 line-clamp-2 mb-3">{scheme.description}</p>
          )}
          <div className="flex flex-wrap gap-2">
            {scheme.category && (
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                {scheme.category.name}
              </span>
            )}
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700 capitalize">
              {scheme.level}
            </span>
            {scheme.tags.slice(0, 2).map((tag) => (
              <span
                key={tag.id}
                className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700"
              >
                {tag.name}
              </span>
            ))}
          </div>
        </div>
        {scheme.featured && (
          <span className="shrink-0 text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded">
            {t("scheme_detail.featured")}
          </span>
        )}
      </div>
    </Link>
  );
}
