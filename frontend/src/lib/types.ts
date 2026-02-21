export interface Category {
  id: string;
  name: string;
  slug: string;
  icon: string | null;
  display_order: number;
  scheme_count: number;
}

export interface State {
  id: string;
  name: string;
  slug: string;
  code: string;
  is_ut: boolean;
  scheme_count: number;
}

export interface Ministry {
  id: string;
  name: string;
  slug: string;
  level: string;
  scheme_count: number;
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
}

export interface FAQ {
  question: string;
  answer: string;
}

export interface SchemeListItem {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  level: string;
  category: Category | null;
  tags: Tag[];
  featured: boolean;
}

export interface SchemeDetail extends SchemeListItem {
  benefits: string | null;
  eligibility_criteria: string | null;
  application_process: string | null;
  documents_required: string | null;
  official_link: string | null;
  target_gender: string[] | null;
  min_age: number | null;
  max_age: number | null;
  target_social_category: string[] | null;
  target_income_max: number | null;
  is_disability: boolean | null;
  is_student: boolean | null;
  is_bpl: boolean | null;
  status: string;
  ministry: Ministry | null;
  states: State[];
  faqs: FAQ[];
  created_at: string | null;
}

export interface PaginatedSchemes {
  items: SchemeListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  content_original?: string;
  schemes?: SchemeListItem[];
  suggestions?: { text: string }[];
  audioBase64?: string;
}

export interface SearchResult {
  scheme: SchemeListItem;
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}
