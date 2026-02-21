"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { getSchemes, getCategories, getStates } from "@/lib/api";
import type { PaginatedSchemes, Category, State } from "@/lib/types";
import SchemeCard from "@/components/schemes/SchemeCard";
import Pagination from "@/components/ui/Pagination";
import { useLanguage } from "@/context/LanguageContext";

export default function SchemesPage() {
  return (
    <Suspense fallback={<div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500">Loading...</div>}>
      <SchemesContent />
    </Suspense>
  );
}

function SchemesContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { language, t } = useLanguage();
  const [data, setData] = useState<PaginatedSchemes | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [states, setStates] = useState<State[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get("search") || "");

  const page = Number(searchParams.get("page") || "1");
  const category = searchParams.get("category") || "";
  const state = searchParams.get("state") || "";
  const level = searchParams.get("level") || "";

  useEffect(() => {
    Promise.all([getCategories(language), getStates(language)])
      .then(([cats, sts]) => {
        setCategories(cats);
        setStates(sts);
      })
      .catch(() => {});
  }, [language]);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page), page_size: "12" };
    if (category) params.category = category;
    if (state) params.state = state;
    if (level) params.level = level;
    if (search) params.search = search;

    getSchemes(params, language)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [page, category, state, level, search, language]);

  function updateParams(updates: Record<string, string>) {
    const params = new URLSearchParams(searchParams.toString());
    Object.entries(updates).forEach(([k, v]) => {
      if (v) params.set(k, v);
      else params.delete(k);
    });
    // Only reset to page 1 if the update isn't a pagination change
    if (!("page" in updates)) {
      params.set("page", "1");
    }
    router.push(`/schemes?${params.toString()}`);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">{t("schemes_page.title")}</h1>

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <input
            type="text"
            placeholder={t("schemes_page.search_placeholder")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && updateParams({ search })}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
          />
          <select
            value={category}
            onChange={(e) => updateParams({ category: e.target.value })}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">{t("common.all_categories")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.slug}>{c.name}</option>
            ))}
          </select>
          <select
            value={state}
            onChange={(e) => updateParams({ state: e.target.value })}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">{t("common.all_states")}</option>
            {states.map((s) => (
              <option key={s.id} value={s.slug}>{s.name}</option>
            ))}
          </select>
          <select
            value={level}
            onChange={(e) => updateParams({ level: e.target.value })}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="">{t("common.all_levels")}</option>
            <option value="central">{t("common.central")}</option>
            <option value="state">{t("common.state")}</option>
          </select>
          <button
            onClick={() => updateParams({ search })}
            className="px-4 py-2 bg-emerald-600 text-white rounded-md text-sm font-medium hover:bg-emerald-700"
          >
            {t("common.search")}
          </button>
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <div className="text-center py-12 text-gray-500">{t("schemes_page.loading")}</div>
      ) : data && data.items.length > 0 ? (
        <>
          <p className="text-sm text-gray-500 mb-4">
            {t("schemes_page.showing")
              .replace("{start}", String((data.page - 1) * data.page_size + 1))
              .replace("{end}", String(Math.min(data.page * data.page_size, data.total)))
              .replace("{total}", String(data.total))}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {data.items.map((scheme) => (
              <SchemeCard key={scheme.id} scheme={scheme} />
            ))}
          </div>
          <Pagination
            page={data.page}
            totalPages={data.total_pages}
            onPageChange={(p) => updateParams({ page: String(p) })}
          />
        </>
      ) : (
        <div className="text-center py-12 text-gray-500">
          {t("schemes_page.no_results")}
        </div>
      )}
    </div>
  );
}
