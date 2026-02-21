"use client";

import EligibilityWizard from "@/components/eligibility/EligibilityWizard";
import { useLanguage } from "@/context/LanguageContext";

export default function FindSchemePage() {
  const { t } = useLanguage();

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">{t("eligibility.title")}</h1>
        <p className="text-gray-600 mt-2">{t("eligibility.subtitle")}</p>
      </div>
      <EligibilityWizard />
    </div>
  );
}
