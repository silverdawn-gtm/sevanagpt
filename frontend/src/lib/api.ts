const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

function buildQS(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  return "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&");
}

function langParam(lang?: string): string {
  return lang && lang !== "en" ? `lang=${lang}` : "";
}

function appendLang(qs: string, lang?: string): string {
  const lp = langParam(lang);
  if (!lp) return qs;
  return qs ? `${qs}&${lp}` : `?${lp}`;
}

// Schemes
export async function getSchemes(params?: Record<string, string>, lang?: string) {
  let qs = params ? "?" + new URLSearchParams(params).toString() : "";
  qs = appendLang(qs, lang);
  return fetchAPI<import("./types").PaginatedSchemes>(`/schemes${qs}`);
}

export async function getScheme(slug: string, lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<import("./types").SchemeDetail>(`/schemes/${slug}${qs ? `?${qs}` : ""}`);
}

export async function getFeaturedSchemes(lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<import("./types").SchemeListItem[]>(`/schemes/featured${qs ? `?${qs}` : ""}`);
}

// Categories
export async function getCategories(lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<import("./types").Category[]>(`/categories${qs ? `?${qs}` : ""}`);
}

export async function getCategory(slug: string, lang?: string, page?: number, pageSize?: number) {
  const qs = buildQS({ lang: lang !== "en" ? lang : undefined, page, page_size: pageSize });
  return fetchAPI<{ category: import("./types").Category; schemes: import("./types").SchemeListItem[]; total?: number }>(
    `/categories/${slug}${qs}`
  );
}

// States
export async function getStates(lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<import("./types").State[]>(`/states${qs ? `?${qs}` : ""}`);
}

export async function getState(slug: string, lang?: string, page?: number, pageSize?: number, level?: string) {
  const qs = buildQS({ lang: lang !== "en" ? lang : undefined, page, page_size: pageSize, level: level || undefined });
  return fetchAPI<{ state: import("./types").State; schemes: import("./types").SchemeListItem[]; total?: number }>(
    `/states/${slug}${qs}`
  );
}

// Ministries
export async function getMinistries(lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<import("./types").Ministry[]>(`/ministries${qs ? `?${qs}` : ""}`);
}

export async function getMinistry(slug: string, lang?: string, page?: number, pageSize?: number) {
  const qs = buildQS({ lang: lang !== "en" ? lang : undefined, page, page_size: pageSize });
  return fetchAPI<{ ministry: import("./types").Ministry; schemes: import("./types").SchemeListItem[]; total?: number }>(
    `/ministries/${slug}${qs}`
  );
}

// Search
export async function searchSchemes(body: Record<string, unknown>, lang?: string) {
  // language is passed inside the request body for POST /search
  const payload = { ...body, language: lang || "en" };
  return fetchAPI<import("./types").SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Eligibility
export async function checkEligibility(body: Record<string, unknown>, lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<{
    results: {
      scheme: import("./types").SchemeListItem;
      match_score: number;
      matched_criteria: string[];
    }[];
    total: number;
    profile: Record<string, unknown>;
  }>(`/eligibility/check${qs ? `?${qs}` : ""}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getEligibilityOptions(lang?: string) {
  const qs = langParam(lang);
  return fetchAPI<{
    genders: string[];
    social_categories: string[];
    states: { code: string; name: string; is_ut: boolean }[];
  }>(`/eligibility/options${qs ? `?${qs}` : ""}`);
}

// Chat
export async function sendChatMessage(body: {
  message: string;
  session_id: string;
  language?: string;
}) {
  return fetchAPI<{
    reply: string;
    schemes: import("./types").SchemeListItem[];
    suggestions: { text: string }[];
    session_id: string;
    fsm_state: string;
  }>("/chat/message", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
