"use client";

import Link from "next/link";

interface MobileHeaderProps {
  onMenuToggle: () => void;
}

export default function MobileHeader({ onMenuToggle }: MobileHeaderProps) {
  return (
    <header className="lg:hidden sticky top-0 z-30 bg-gray-900 text-white border-b border-gray-800">
      <div className="flex items-center justify-between px-4 h-14">
        <button
          onClick={onMenuToggle}
          className="p-2 -ml-2 rounded-md hover:bg-gray-800"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <Link href="/" className="text-lg font-bold text-emerald-400">
          SevanaGPT
        </Link>
        <div className="w-9" /> {/* Spacer for centering */}
      </div>
    </header>
  );
}
