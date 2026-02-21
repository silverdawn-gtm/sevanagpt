"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getSchemes, getCategories, getStates } from "@/lib/api";
import type { SchemeListItem, Category, State } from "@/lib/types";
import SchemeCard from "@/components/schemes/SchemeCard";
import { useLanguage } from "@/context/LanguageContext";
import { HERO_STATS, CATEGORY_ICONS } from "@/lib/constants";

export default function HomePage() {
  const { language, t } = useLanguage();
  const [featured, setFeatured] = useState<SchemeListItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [states, setStates] = useState<State[]>([]);

  useEffect(() => {
    Promise.all([
      getSchemes({ page: "1", page_size: "6" }, language),
      getCategories(language),
      getStates(language),
    ])
      .then(([schemesRes, catsRes, statesRes]) => {
        setFeatured(schemesRes.items);
        setCategories(catsRes.slice(0, 8));
        setStates(statesRes);
      })
      .catch(() => {});
  }, [language]);

  const statesList = states.filter((s) => !s.is_ut).slice(0, 12);
  const utList = states.filter((s) => s.is_ut).slice(0, 8);

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-emerald-600 via-emerald-700 to-teal-800 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16 md:py-24">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-3xl md:text-4xl lg:text-5xl font-bold leading-tight mb-6">
              {t("hero.title")}
            </h1>
            <p className="text-emerald-100 text-lg md:text-xl mb-10">
              {t("hero.subtitle")}
            </p>

            <div className="flex flex-wrap gap-4 justify-center mb-12">
              <Link
                href="/find-scheme"
                className="inline-flex items-center px-8 py-3.5 bg-white text-emerald-700 font-semibold rounded-lg hover:bg-emerald-50 transition-colors shadow-lg"
              >
                {t("hero.cta_eligibility")}
              </Link>
              <Link
                href="/chat"
                className="inline-flex items-center px-8 py-3.5 bg-emerald-500 text-white font-semibold rounded-lg hover:bg-emerald-400 transition-colors border border-emerald-400 shadow-lg"
              >
                {t("hero.cta_chat")}
              </Link>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-2xl mx-auto">
              {HERO_STATS.map((stat) => (
                <div key={stat.labelKey} className="bg-white/10 backdrop-blur rounded-lg p-4 text-center">
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <div className="text-emerald-200 text-sm">{t(stat.labelKey)}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Browse by Category */}
      {categories.length > 0 && (
        <section className="py-12 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-bold text-gray-900">{t("browse.by_category")}</h2>
              <Link href="/categories" className="text-emerald-600 hover:text-emerald-700 text-sm font-medium">
                {t("browse.view_all")} →
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
              {categories.map((cat) => (
                <Link
                  key={cat.id}
                  href={`/categories/${cat.slug}`}
                  className="flex items-center gap-3 p-4 rounded-lg border border-gray-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors group"
                >
                  <span className="text-2xl">{(cat.icon && CATEGORY_ICONS[cat.icon]) || "📋"}</span>
                  <div>
                    <div className="font-medium text-gray-900 group-hover:text-emerald-700">{cat.name}</div>
                    <div className="text-sm text-gray-500">{cat.scheme_count} {t("browse.schemes")}</div>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Featured Schemes */}
      {featured.length > 0 && (
        <section className="py-12 bg-gray-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-bold text-gray-900">{t("browse.featured")}</h2>
              <Link href="/schemes" className="text-emerald-600 hover:text-emerald-700 text-sm font-medium">
                {t("browse.view_all")} →
              </Link>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {featured.map((scheme) => (
                <SchemeCard key={scheme.id} scheme={scheme} />
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Browse by State */}
      {statesList.length > 0 && (
        <section className="py-12 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center mb-8">
              <h2 className="text-2xl font-bold text-gray-900">{t("browse.by_state")}</h2>
              <Link href="/states" className="text-emerald-600 hover:text-emerald-700 text-sm font-medium">
                {t("browse.view_all")} →
              </Link>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
              {statesList.map((s) => (
                <Link
                  key={s.id}
                  href={`/states/${s.slug}`}
                  className="text-center p-3 rounded-lg border border-gray-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors"
                >
                  <div className="font-medium text-sm text-gray-900">{s.name}</div>
                  <div className="text-xs text-gray-500">{s.scheme_count} {t("browse.schemes")}</div>
                </Link>
              ))}
            </div>
            {utList.length > 0 && (
              <>
                <h3 className="text-lg font-semibold text-gray-700 mt-8 mb-4">{t("browse.union_territories")}</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {utList.map((s) => (
                    <Link
                      key={s.id}
                      href={`/states/${s.slug}`}
                      className="text-center p-3 rounded-lg border border-gray-200 hover:border-emerald-300 hover:bg-emerald-50 transition-colors"
                    >
                      <div className="font-medium text-sm text-gray-900">{s.name}</div>
                      <div className="text-xs text-gray-500">{s.scheme_count} {t("browse.schemes")}</div>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* CTA Section */}
      <section className="py-16 bg-emerald-600 text-white">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">{t("cta.title")}</h2>
          <p className="text-emerald-100 mb-8 text-lg">{t("cta.subtitle")}</p>
          <Link
            href="/chat"
            className="inline-flex items-center px-8 py-3 bg-white text-emerald-700 font-semibold rounded-lg hover:bg-emerald-50 transition-colors"
          >
            {t("cta.start_chatting")}
          </Link>
        </div>
      </section>
    </div>
  );
}
