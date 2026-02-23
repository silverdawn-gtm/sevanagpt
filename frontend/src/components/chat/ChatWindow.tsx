"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { ChatMessage } from "@/lib/types";
import clsx from "clsx";
import { useLanguage } from "@/context/LanguageContext";
import ReadAloudButton from "@/components/ui/ReadAloudButton";

interface ChatWindowProps {
  messages: ChatMessage[];
  loading: boolean;
}

export default function ChatWindow({ messages, loading }: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const { t } = useLanguage();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {messages.length === 0 && (
        <div className="text-center text-gray-400 py-12">
          <div className="text-5xl mb-4">💬</div>
          <p className="text-lg font-medium">{t("chat.welcome")}</p>
          <p className="text-sm mt-2">{t("chat.welcome_sub")}</p>
        </div>
      )}

      {messages.map((msg, i) => (
        <div key={i} className={clsx("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
          <div
            className={clsx(
              "max-w-[80%] rounded-lg px-4 py-3",
              msg.role === "user"
                ? "bg-emerald-600 text-white"
                : "bg-white border border-gray-200 text-gray-900"
            )}
          >
            <div className="whitespace-pre-wrap text-sm">{msg.content}</div>

            {/* Read aloud button for assistant messages */}
            {msg.role === "assistant" && (
              <div className="mt-2">
                <ReadAloudButton text={msg.content} />
              </div>
            )}

            {/* Scheme cards */}
            {msg.schemes && msg.schemes.length > 0 && (
              <div className="mt-3 space-y-2">
                {msg.schemes.map((scheme) => (
                  <Link
                    key={scheme.id}
                    href={`/schemes/${scheme.slug}`}
                    className="block p-3 bg-gray-50 border border-gray-200 rounded-md hover:bg-gray-100 transition-colors"
                  >
                    <div className="font-medium text-sm text-gray-900">{scheme.name}</div>
                    {scheme.description && (
                      <div className="text-xs text-gray-600 mt-1 line-clamp-2">{scheme.description}</div>
                    )}
                    <div className="flex gap-1 mt-2">
                      {scheme.tags?.slice(0, 2).map((tag) => (
                        <span key={tag.id} className="text-xs px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full">
                          {tag.name}
                        </span>
                      ))}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}

      {loading && (
        <div className="flex justify-start">
          <div className="bg-white border border-gray-200 rounded-lg px-4 py-3">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
          </div>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
