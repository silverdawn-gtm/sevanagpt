"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useLanguage } from "@/context/LanguageContext";
import { useChatHistory } from "@/hooks/useChatHistory";
import LanguageSwitcher from "./LanguageSwitcher";

interface SidebarProps {
  open: boolean;
  onClose: () => void;
}

export default function Sidebar({ open, onClose }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useLanguage();
  const { conversations, deleteConversation } = useChatHistory();

  const browseLinks = [
    { href: "/schemes", label: t("nav.schemes") },
    { href: "/categories", label: t("nav.categories") },
    { href: "/states", label: t("nav.states") },
    { href: "/ministries", label: t("nav.ministries") },
    { href: "/find-scheme", label: t("nav.find_scheme") },
  ];

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          "fixed lg:static inset-y-0 left-0 z-50 w-72 bg-gray-900 text-gray-100 flex flex-col transition-transform duration-200 ease-in-out",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-gray-800">
          <Link href="/" onClick={onClose} className="flex items-center gap-2">
            <span className="text-xl font-bold text-emerald-400">SevanaGPT</span>
          </Link>
          <button
            onClick={onClose}
            className="lg:hidden p-1 rounded hover:bg-gray-800"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* New Chat button */}
        <div className="px-3 py-3">
          <Link
            href="/"
            onClick={onClose}
            className="flex items-center gap-2 w-full px-3 py-2.5 text-sm font-medium rounded-lg border border-gray-700 hover:bg-gray-800 transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {t("sidebar.new_chat")}
          </Link>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-3">
          {/* Chat History */}
          {conversations.length > 0 && (
            <div className="mb-4">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                {t("sidebar.chat_history")}
              </div>
              <div className="space-y-0.5">
                {conversations.slice(0, 20).map((conv) => (
                  <div
                    key={conv.id}
                    className="group flex items-center gap-1 rounded-lg hover:bg-gray-800"
                  >
                    <Link
                      href="/"
                      onClick={onClose}
                      className="flex-1 px-3 py-2 text-sm text-gray-300 truncate"
                    >
                      {conv.title}
                    </Link>
                    <button
                      onClick={() => deleteConversation(conv.id)}
                      className="hidden group-hover:block p-1 mr-1 text-gray-500 hover:text-red-400 rounded"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Browse section */}
          <div className="mb-4">
            <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
              {t("sidebar.browse")}
            </div>
            <div className="space-y-0.5">
              {browseLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onClose}
                  className={clsx(
                    "flex items-center gap-2 px-3 py-2 text-sm rounded-lg transition-colors",
                    pathname === link.href || pathname.startsWith(link.href + "/")
                      ? "bg-gray-800 text-emerald-400"
                      : "text-gray-300 hover:bg-gray-800 hover:text-white"
                  )}
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </div>

        {/* Bottom: Language switcher */}
        <div className="px-4 py-3 border-t border-gray-800">
          <div className="text-xs text-gray-500 mb-2">{t("sidebar.language")}</div>
          <LanguageSwitcher />
        </div>
      </aside>
    </>
  );
}
