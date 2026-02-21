"use client";

import { useState, useEffect, useCallback } from "react";

export interface ChatConversation {
  id: string;
  title: string;
  createdAt: number;
}

const STORAGE_KEY = "sevanagpt_chat_history";

function loadFromStorage(): ChatConversation[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveToStorage(conversations: ChatConversation[]) {
  if (typeof window === "undefined") return;
  localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
}

export function useChatHistory() {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);

  useEffect(() => {
    setConversations(loadFromStorage());
  }, []);

  const createConversation = useCallback((id: string, title: string) => {
    setConversations((prev) => {
      // Don't add duplicate
      if (prev.some((c) => c.id === id)) return prev;
      const updated = [{ id, title, createdAt: Date.now() }, ...prev].slice(0, 50);
      saveToStorage(updated);
      return updated;
    });
  }, []);

  const updateConversationTitle = useCallback((id: string, title: string) => {
    setConversations((prev) => {
      const updated = prev.map((c) => (c.id === id ? { ...c, title } : c));
      saveToStorage(updated);
      return updated;
    });
  }, []);

  const deleteConversation = useCallback((id: string) => {
    setConversations((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      saveToStorage(updated);
      return updated;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setConversations([]);
    saveToStorage([]);
  }, []);

  return {
    conversations,
    createConversation,
    updateConversationTitle,
    deleteConversation,
    clearHistory,
  };
}
