"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getScheme } from "@/lib/api";
import type { SchemeDetail } from "@/lib/types";
import { useLanguage } from "@/context/LanguageContext";

export default function SchemeDetailPage() {
  const params = useParams<{ slug: string }>();
  const { language, t } = useLanguage();
  const [scheme, setScheme] = useState<SchemeDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!params.slug) return;
    setLoading(true);
    getScheme(params.slug, language)
      .then(setScheme)
      .catch(() => setScheme(null))
      .finally(() => setLoading(false));
  }, [params.slug, language]);

  if (loading) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500">{t("schemes_page.loading")}</div>;
  }

  if (!scheme) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500">{t("not_found.title")}</div>;
  }

  const sectionKeys = [
    { key: "description", content: scheme.description },
    { key: "benefits", content: scheme.benefits },
    { key: "eligibility_criteria", content: scheme.eligibility_criteria },
    { key: "application_process", content: scheme.application_process },
    { key: "documents_required", content: scheme.documents_required },
  ];

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/schemes" className="hover:text-emerald-600">{t("scheme_detail.breadcrumb_schemes")}</Link>
        <span className="mx-2">/</span>
        <span className="text-gray-900">{scheme.name}</span>
      </nav>

      {/* Header */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 mb-6">
        <h1 className="text-2xl md:text-3xl font-bold text-gray-900 mb-4">{scheme.name}</h1>
        <div className="flex flex-wrap gap-2 mb-4">
          {scheme.category && (
            <Link
              href={`/categories/${scheme.category.slug}`}
              className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800 hover:bg-blue-200"
            >
              {scheme.category.name}
            </Link>
          )}
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700 capitalize">
            {scheme.level}
          </span>
          {scheme.tags.map((tag) => (
            <span
              key={tag.id}
              className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-emerald-100 text-emerald-700"
            >
              {tag.name}
            </span>
          ))}
        </div>
        {scheme.ministry && (
          <p className="text-sm text-gray-600">
            <span className="font-medium">{t("scheme_detail.ministry_label")}</span>{" "}
            <Link href={`/ministries/${scheme.ministry.slug}`} className="text-emerald-600 hover:underline">
              {scheme.ministry.name}
            </Link>
          </p>
        )}
        {scheme.states.length > 0 && (
          <p className="text-sm text-gray-600 mt-1">
            <span className="font-medium">{t("scheme_detail.states_label")}</span>{" "}
            {scheme.states.map((s) => s.name).join(", ")}
          </p>
        )}
        <a
          href={scheme.official_link || `https://www.myscheme.gov.in/schemes/${scheme.slug}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center mt-3 text-sm text-emerald-600 hover:underline"
        >
          {scheme.official_link ? t("scheme_detail.official_website") : t("scheme_detail.view_on_myscheme")} &rarr;
        </a>
      </div>

      {/* Content Sections */}
      {sectionKeys.map(
        (section) =>
          section.content && (
            <div key={section.key} className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-3">{t(`scheme_detail.${section.key}`)}</h2>
              <div className="text-gray-700 whitespace-pre-line">{section.content}</div>
            </div>
          )
      )}

      {/* Eligibility Quick View */}
      {(scheme.target_gender || scheme.min_age || scheme.max_age || scheme.target_social_category || scheme.target_income_max) && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">{t("scheme_detail.eligibility_glance")}</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {scheme.target_gender && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.gender")}</div>
                <div className="text-sm font-medium capitalize">{scheme.target_gender.join(", ")}</div>
              </div>
            )}
            {(scheme.min_age || scheme.max_age) && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.age")}</div>
                <div className="text-sm font-medium">
                  {scheme.min_age && `${scheme.min_age}+`}
                  {scheme.min_age && scheme.max_age && " to "}
                  {scheme.max_age && `${scheme.max_age} ${t("scheme_detail.years")}`}
                </div>
              </div>
            )}
            {scheme.target_social_category && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.social_category")}</div>
                <div className="text-sm font-medium">{scheme.target_social_category.join(", ")}</div>
              </div>
            )}
            {scheme.target_income_max && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.max_income")}</div>
                <div className="text-sm font-medium">Rs. {scheme.target_income_max.toLocaleString()}</div>
              </div>
            )}
            {scheme.is_disability && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.disability")}</div>
                <div className="text-sm font-medium">{t("scheme_detail.yes")}</div>
              </div>
            )}
            {scheme.is_student && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.student")}</div>
                <div className="text-sm font-medium">{t("scheme_detail.yes")}</div>
              </div>
            )}
            {scheme.is_bpl && (
              <div>
                <div className="text-xs text-gray-500 uppercase">{t("scheme_detail.bpl")}</div>
                <div className="text-sm font-medium">{t("scheme_detail.yes")}</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* FAQs */}
      {scheme.faqs.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 mb-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">{t("scheme_detail.faqs")}</h2>
          <div className="space-y-4">
            {scheme.faqs.map((faq, i) => (
              <div key={i}>
                <h3 className="font-medium text-gray-900">{faq.question}</h3>
                <p className="text-sm text-gray-600 mt-1">{faq.answer}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
