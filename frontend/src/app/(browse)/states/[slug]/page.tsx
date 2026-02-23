"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getState } from "@/lib/api";
import type { State, SchemeListItem } from "@/lib/types";
import SchemeCard from "@/components/schemes/SchemeCard";
import Pagination from "@/components/ui/Pagination";
import { useLanguage } from "@/context/LanguageContext";

const PAGE_SIZE = 24;

export default function StateDetailPage() {
  const params = useParams<{ slug: string }>();
  const { language, t } = useLanguage();
  const [state, setState] = useState<State | null>(null);
  const [schemes, setSchemes] = useState<SchemeListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [level, setLevel] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params.slug) return;
    setLoading(true);
    getState(params.slug, language, page, PAGE_SIZE, level)
      .then((data) => {
        setState(data.state);
        setSchemes(data.schemes);
        setTotal(data.total ?? data.schemes.length);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [params.slug, language, page, level]);

  useEffect(() => { setPage(1); }, [language, level]);

  if (loading) {
    return <div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500">{t("schemes_page.loading")}</div>;
  }

  if (!state) {
    return <div className="max-w-7xl mx-auto px-4 py-8 text-center text-gray-500">{t("not_found.title")}</div>;
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/states" className="hover:text-emerald-600">{t("browse.by_state")}</Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900">{state.name}</span>
      </nav>

      <h1 className="text-3xl font-bold text-gray-900 mb-2">{state.name}</h1>
      <p className="text-gray-600 mb-4">{total} {t("browse.schemes")}</p>

      <div className="flex items-center gap-2 mb-6">
        <button
          onClick={() => setLevel("")}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${level === "" ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
        >
          {t("common.all_levels")}
        </button>
        <button
          onClick={() => setLevel("state")}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${level === "state" ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
        >
          {t("common.state")} {t("browse.schemes")}
        </button>
        <button
          onClick={() => setLevel("central")}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${level === "central" ? "bg-emerald-600 text-white" : "bg-gray-100 text-gray-700 hover:bg-gray-200"}`}
        >
          {t("common.central")} {t("browse.schemes")}
        </button>
      </div>

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
