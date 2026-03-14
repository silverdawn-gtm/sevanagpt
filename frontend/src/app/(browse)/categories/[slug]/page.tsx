"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getCategory } from "@/lib/api";
import type { Category, SchemeListItem } from "@/lib/types";
import SchemeCard from "@/components/schemes/SchemeCard";
import Pagination from "@/components/ui/Pagination";
import { useLanguage } from "@/context/LanguageContext";

const PAGE_SIZE = 24;

export default function CategoryDetailPage() {
  const params = useParams<{ slug: string }>();
  const { language, t } = useLanguage();
  const [category, setCategory] = useState<Category | null>(null);
  const [schemes, setSchemes] = useState<SchemeListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params.slug) return;
    setLoading(true);
    getCategory(params.slug, language, page, PAGE_SIZE)
      .then((data) => {
        setCategory(data.category);
        setSchemes(data.schemes);
        setTotal(data.total !== undefined ? data.total : data.schemes.length);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [params.slug, language, page]);

  // Reset to page 1 when language changes
  useEffect(() => { setPage(1); }, [language]);

  if (loading) {
    return <div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500">{t("schemes_page.loading")}</div>;
  }

  if (!category) {
    return <div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500">{t("not_found.title")}</div>;
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/categories" className="hover:text-emerald-600">{t("browse.by_category")}</Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900">{category.name}</span>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-2">{category.name}</h1>
      <p className="text-gray-600 mb-8">{total} {t("browse.schemes")}</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {schemes.map((scheme) => (
          <SchemeCard key={scheme.id} scheme={scheme} />
        ))}
      </div>

      {schemes.length === 0 && (
        <div className="text-center py-12 text-gray-500">{t("schemes_page.no_results")}</div>
      )}

      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
