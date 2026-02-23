"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { checkEligibility, getEligibilityOptions } from "@/lib/api";
import type { SchemeListItem } from "@/lib/types";
import clsx from "clsx";
import { useLanguage } from "@/context/LanguageContext";

interface EligibilityOptions {
  genders: string[];
  social_categories: string[];
  states: { code: string; name: string; is_ut: boolean }[];
}

interface EligibilityResult {
  scheme: SchemeListItem;
  match_score: number;
  matched_criteria: string[];
}

interface Profile {
  gender: string;
  age: string;
  state_code: string;
  social_category: string;
  income: string;
  is_disability: boolean;
  is_student: boolean;
  is_bpl: boolean;
}

export default function EligibilityWizard() {
  const [step, setStep] = useState(0);
  const { language, t } = useLanguage();
  const [profile, setProfile] = useState<Profile>({
    gender: "",
    age: "",
    state_code: "",
    social_category: "",
    income: "",
    is_disability: false,
    is_student: false,
    is_bpl: false,
  });
  const [options, setOptions] = useState<EligibilityOptions | null>(null);
  const [results, setResults] = useState<EligibilityResult[] | null>(null);
  const [loading, setLoading] = useState(false);

  const STEPS = [
    { key: "gender", title: t("eligibility.gender_title"), description: t("eligibility.gender_desc") },
    { key: "age", title: t("eligibility.age_title"), description: t("eligibility.age_desc") },
    { key: "state", title: t("eligibility.location_title"), description: t("eligibility.location_desc") },
    { key: "category", title: t("eligibility.category_title"), description: t("eligibility.category_desc") },
    { key: "disability", title: t("eligibility.disability_title"), description: t("eligibility.disability_desc") },
    { key: "student", title: t("eligibility.student_title"), description: t("eligibility.student_desc") },
    { key: "income", title: t("eligibility.income_title"), description: t("eligibility.income_desc") },
    { key: "bpl", title: t("eligibility.bpl_title"), description: t("eligibility.bpl_desc") },
  ];

  useEffect(() => {
    getEligibilityOptions(language).then(setOptions).catch(() => {});
  }, [language]);

  async function handleSubmit() {
    setLoading(true);
    try {
      const body: Record<string, unknown> = {};
      if (profile.gender) body.gender = profile.gender.toLowerCase();
      if (profile.age) body.age = parseInt(profile.age);
      if (profile.state_code) body.state_code = profile.state_code;
      if (profile.social_category) body.social_category = profile.social_category;
      if (profile.income) body.income = parseFloat(profile.income);
      body.is_disability = profile.is_disability;
      body.is_student = profile.is_student;
      body.is_bpl = profile.is_bpl;

      const data = await checkEligibility(body, language);
      setResults(data.results);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  function handleNext() {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    } else {
      handleSubmit();
    }
  }

  function handleBack() {
    if (step > 0) setStep(step - 1);
  }

  function handleReset() {
    setStep(0);
    setResults(null);
    setProfile({
      gender: "",
      age: "",
      state_code: "",
      social_category: "",
      income: "",
      is_disability: false,
      is_student: false,
      is_bpl: false,
    });
  }

  // Show results
  if (results !== null) {
    return (
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900">
            {t("eligibility.schemes_found").replace("{count}", String(results.length))}
          </h2>
          <button
            onClick={handleReset}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            {t("eligibility.start_over")}
          </button>
        </div>

        {results.length === 0 ? (
          <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
            <p className="text-gray-600">
              {t("eligibility.no_matches")}{" "}
              <Link href="/chat" className="text-emerald-600 hover:underline">
                {t("eligibility.chat_for_recs")}
              </Link>{" "}
              {t("eligibility.for_personalized")}
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {results.map((r) => (
              <div key={r.scheme.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <Link
                      href={`/schemes/${r.scheme.slug}`}
                      className="text-lg font-semibold text-gray-900 hover:text-emerald-600"
                    >
                      {r.scheme.name}
                    </Link>
                    {r.scheme.description && (
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">{r.scheme.description}</p>
                    )}
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {r.matched_criteria.map((c, i) => (
                        <span
                          key={i}
                          className="text-xs px-2 py-0.5 bg-green-100 text-green-700 rounded-full"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="ml-4 flex-shrink-0">
                    <div
                      className={clsx(
                        "text-sm font-bold px-3 py-1 rounded-full",
                        r.match_score >= 0.8
                          ? "bg-green-100 text-green-700"
                          : r.match_score >= 0.5
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-gray-100 text-gray-600"
                      )}
                    >
                      {Math.round(r.match_score * 100)}% {t("scheme_detail.match")}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  const currentStep = STEPS[step];

  return (
    <div>
      {/* Progress bar */}
      <div className="mb-6">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>{t("eligibility.step_of").replace("{current}", String(step + 1)).replace("{total}", String(STEPS.length))}</span>
          <span>{currentStep.title}</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-emerald-600 h-2 rounded-full transition-all"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-1">{currentStep.title}</h3>
        <p className="text-sm text-gray-500 mb-4">{currentStep.description}</p>

        {/* Step content */}
        <div className="mb-6">
          {currentStep.key === "gender" && (
            <div className="grid grid-cols-3 gap-3">
              {(options?.genders || ["Male", "Female", "Transgender"]).map((g) => (
                <button
                  key={g}
                  onClick={() => setProfile({ ...profile, gender: g })}
                  className={clsx(
                    "px-4 py-3 rounded-lg border text-sm font-medium transition-colors",
                    profile.gender === g
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-gray-300 hover:bg-gray-50"
                  )}
                >
                  {g}
                </button>
              ))}
            </div>
          )}

          {currentStep.key === "age" && (
            <input
              type="number"
              value={profile.age}
              onChange={(e) => setProfile({ ...profile, age: e.target.value })}
              placeholder={t("eligibility.age_placeholder")}
              min={0}
              max={120}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            />
          )}

          {currentStep.key === "state" && (
            <select
              value={profile.state_code}
              onChange={(e) => setProfile({ ...profile, state_code: e.target.value })}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
            >
              <option value="">{t("eligibility.location_placeholder")}</option>
              {options?.states.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name} {s.is_ut ? "(UT)" : ""}
                </option>
              ))}
            </select>
          )}

          {currentStep.key === "category" && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {(options?.social_categories || ["General", "SC", "ST", "OBC", "EWS"]).map((c) => (
                <button
                  key={c}
                  onClick={() => setProfile({ ...profile, social_category: c })}
                  className={clsx(
                    "px-4 py-3 rounded-lg border text-sm font-medium transition-colors",
                    profile.social_category === c
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-gray-300 hover:bg-gray-50"
                  )}
                >
                  {c}
                </button>
              ))}
            </div>
          )}

          {currentStep.key === "disability" && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: t("scheme_detail.yes"), value: true },
                { label: t("scheme_detail.no"), value: false },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setProfile({ ...profile, is_disability: opt.value })}
                  className={clsx(
                    "px-4 py-3 rounded-lg border text-sm font-medium transition-colors",
                    profile.is_disability === opt.value
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-gray-300 hover:bg-gray-50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {currentStep.key === "student" && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: t("scheme_detail.yes"), value: true },
                { label: t("scheme_detail.no"), value: false },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setProfile({ ...profile, is_student: opt.value })}
                  className={clsx(
                    "px-4 py-3 rounded-lg border text-sm font-medium transition-colors",
                    profile.is_student === opt.value
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-gray-300 hover:bg-gray-50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}

          {currentStep.key === "income" && (
            <div>
              <input
                type="number"
                value={profile.income}
                onChange={(e) => setProfile({ ...profile, income: e.target.value })}
                placeholder={t("eligibility.income_placeholder")}
                min={0}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              />
              <p className="text-xs text-gray-400 mt-1">{t("eligibility.income_hint")}</p>
            </div>
          )}

          {currentStep.key === "bpl" && (
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: t("scheme_detail.yes"), value: true },
                { label: t("scheme_detail.no"), value: false },
              ].map((opt) => (
                <button
                  key={opt.label}
                  onClick={() => setProfile({ ...profile, is_bpl: opt.value })}
                  className={clsx(
                    "px-4 py-3 rounded-lg border text-sm font-medium transition-colors",
                    profile.is_bpl === opt.value
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-gray-300 hover:bg-gray-50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Navigation */}
        <div className="flex justify-between">
          <button
            onClick={handleBack}
            disabled={step === 0}
            className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t("eligibility.back")}
          </button>
          <div className="flex gap-2">
            <button
              onClick={handleNext}
              className="px-4 py-2 text-sm rounded-lg transition-colors"
            >
              {t("eligibility.skip")}
            </button>
            <button
              onClick={handleNext}
              disabled={loading}
              className="px-6 py-2 text-sm bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:bg-gray-300 font-medium"
            >
              {loading ? t("eligibility.checking") : step === STEPS.length - 1 ? t("eligibility.find_schemes") : t("eligibility.next")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
