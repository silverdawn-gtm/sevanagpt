"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getStates } from "@/lib/api";
import type { State } from "@/lib/types";
import { useLanguage } from "@/context/LanguageContext";

export default function StatesPage() {
  const { language, t } = useLanguage();
  const [states, setStates] = useState<State[]>([]);

  useEffect(() => {
    getStates(language).then(setStates).catch(() => {});
  }, [language]);

  const statesList = states.filter((s) => !s.is_ut);
  const utList = states.filter((s) => s.is_ut);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-2">{t("browse.by_state")}</h1>
      <p className="text-gray-600 mb-8">{t("browse.state_subtitle")}</p>

      <h2 className="text-xl font-semibold text-gray-900 mb-4">{t("browse.states_label")} ({statesList.length})</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 mb-10">
        {statesList.map((state) => (
          <Link
            key={state.id}
            href={`/states/${state.slug}`}
            className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-emerald-300 transition-all"
          >
            <span className="font-medium text-gray-900">{state.name}</span>
            <span className="text-sm text-gray-500">{state.scheme_count}</span>
          </Link>
        ))}
      </div>

      <h2 className="text-xl font-semibold text-gray-900 mb-4">{t("browse.union_territories")} ({utList.length})</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {utList.map((ut) => (
          <Link
            key={ut.id}
            href={`/states/${ut.slug}`}
            className="flex items-center justify-between p-4 bg-white border border-gray-200 rounded-lg hover:shadow-md hover:border-emerald-300 transition-all"
          >
            <span className="font-medium text-gray-900">{ut.name}</span>
            <span className="text-sm text-gray-500">{ut.scheme_count}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
