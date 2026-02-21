"use client";

import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";

export default function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="bg-gray-900 text-gray-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          <div>
            <h3 className="text-xl font-bold text-white mb-4">{t("site_name")}</h3>
            <p className="text-sm">{t("footer.description")}</p>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3">{t("footer.browse")}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/schemes" className="hover:text-white">{t("footer.all_schemes")}</Link></li>
              <li><Link href="/categories" className="hover:text-white">{t("footer.by_category")}</Link></li>
              <li><Link href="/states" className="hover:text-white">{t("footer.by_state")}</Link></li>
              <li><Link href="/ministries" className="hover:text-white">{t("footer.by_ministry")}</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3">{t("footer.tools")}</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/find-scheme" className="hover:text-white">{t("footer.eligibility_checker")}</Link></li>
              <li><Link href="/chat" className="hover:text-white">{t("footer.ai_chatbot")}</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="font-semibold text-white mb-3">{t("footer.about")}</h4>
            <p className="text-sm">{t("footer.about_text")}</p>
          </div>
        </div>
        <div className="border-t border-gray-700 mt-8 pt-8 text-sm text-center">
          {t("footer.built_with")}
        </div>
      </div>
    </footer>
  );
}
