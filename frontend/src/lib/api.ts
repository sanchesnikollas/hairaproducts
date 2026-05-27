import type { BrandCoverage, BrandSummary, GlobalStats, IngredientSummary, PaginatedResponse, Product, ProductIngredient, QuarantineItem, ReviewQueueItem } from '../types/api';

const BASE_URL = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    ...options,
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

// ── Brands ──

export async function getBrands(): Promise<BrandCoverage[]> {
  return fetchJSON<BrandCoverage[]>('/brands');
}

export async function getBrandCoverage(slug: string): Promise<BrandCoverage> {
  return fetchJSON<BrandCoverage>(`/brands/${slug}/coverage`);
}

// ── Products ──

export interface ProductFilters {
  brand?: string;
  verified_only?: boolean;
  exclude_kits?: boolean;
  search?: string;
  category?: string;
  page?: number;
  per_page?: number;
}

export async function getProducts(filters: ProductFilters = {}): Promise<PaginatedResponse<Product>> {
  const params = new URLSearchParams();
  if (filters.brand) params.set('brand_slug', filters.brand);
  if (filters.verified_only !== undefined) params.set('verified_only', String(filters.verified_only));
  if (filters.exclude_kits !== undefined) params.set('exclude_kits', String(filters.exclude_kits));
  if (filters.search) params.set('search', filters.search);
  if (filters.category) params.set('category', filters.category);
  const perPage = filters.per_page ?? 100;
  params.set('limit', String(perPage));
  if (filters.page) params.set('offset', String(((filters.page ?? 1) - 1) * perPage));
  const qs = params.toString();
  return fetchJSON<PaginatedResponse<Product>>(`/products${qs ? `?${qs}` : ''}`);
}

export function getExportUrl(filters: ProductFilters = {}, format: 'csv' | 'json' = 'csv'): string {
  const params = new URLSearchParams();
  if (filters.brand) params.set('brand_slug', filters.brand);
  if (filters.verified_only !== undefined) params.set('verified_only', String(filters.verified_only));
  if (filters.search) params.set('search', filters.search);
  params.set('format', format);
  return `/api/products/export?${params.toString()}`;
}

export async function getProduct(id: string): Promise<Product> {
  return fetchJSON<Product>(`/products/${id}`);
}

export async function updateProduct(id: string, data: Partial<Product>): Promise<Product> {
  return fetchJSON<Product>(`/products/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

// ── Global Stats ──

export async function getGlobalStats(): Promise<GlobalStats> {
  return fetchJSON<GlobalStats>('/stats');
}

// ── Brand Summaries ──

export async function getBrandSummaries(): Promise<BrandSummary[]> {
  return fetchJSON<BrandSummary[]>('/brands');
}

export async function getBrandProducts(
  slug: string,
  filters: Omit<ProductFilters, 'brand'> = {}
): Promise<PaginatedResponse<Product>> {
  const params = new URLSearchParams();
  if (filters.verified_only !== undefined) params.set('verified_only', String(filters.verified_only));
  if (filters.exclude_kits !== undefined) params.set('exclude_kits', String(filters.exclude_kits));
  if (filters.search) params.set('search', filters.search);
  if (filters.category) params.set('category', filters.category);
  const perPage = filters.per_page ?? 100;
  params.set('limit', String(perPage));
  if (filters.page) params.set('offset', String(((filters.page ?? 1) - 1) * perPage));
  const qs = params.toString();
  return fetchJSON<PaginatedResponse<Product>>(`/brands/${slug}/products${qs ? `?${qs}` : ''}`);
}

export async function getBrandProduct(slug: string, productId: string): Promise<Product> {
  return fetchJSON<Product>(`/brands/${slug}/products/${productId}`);
}

// ── Quarantine ──

export async function getQuarantine(reviewStatus?: string): Promise<QuarantineItem[]> {
  const qs = reviewStatus ? `?review_status=${reviewStatus}` : '';
  return fetchJSON<QuarantineItem[]>(`/quarantine${qs}`);
}

export async function getQuarantineByBrand(brandSlug: string, reviewStatus = 'pending'): Promise<QuarantineItem[]> {
  return fetchJSON<QuarantineItem[]>(`/quarantine?brand=${brandSlug}&review_status=${reviewStatus}`);
}

export async function approveQuarantine(id: string, notes?: string): Promise<{ status: string; quarantine_id: string }> {
  const params = notes ? `?notes=${encodeURIComponent(notes)}` : '';
  return fetchJSON(`/quarantine/${id}/approve${params}`, { method: 'POST' });
}

export async function rejectQuarantine(id: string, notes?: string): Promise<{ status: string; quarantine_id: string }> {
  const params = notes ? `?notes=${encodeURIComponent(notes)}` : '';
  return fetchJSON(`/quarantine/${id}/reject${params}`, { method: 'POST' });
}

// ── Ingredients ──

export async function fetchIngredients(query?: string): Promise<IngredientSummary[]> {
  const params = query ? `?q=${encodeURIComponent(query)}` : '';
  return fetchJSON<IngredientSummary[]>(`/ingredients${params}`);
}

export async function fetchProductIngredients(productId: string): Promise<ProductIngredient[]> {
  return fetchJSON<ProductIngredient[]>(`/products/${productId}/ingredients`);
}

// ── Review Queue ──

export async function fetchReviewQueue(status = 'pending'): Promise<ReviewQueueItem[]> {
  return fetchJSON<ReviewQueueItem[]>(`/review-queue?status=${status}`);
}

export async function resolveReviewItem(itemId: string, status: string, notes?: string): Promise<void> {
  await fetchJSON(`/review-queue/${itemId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, reviewer_notes: notes }),
  });
}

// ── Moon AI ──

export interface MoonMatch {
  hair_type: string;
  score: number;
  reason: string;
}

export interface MoonBreakdown {
  name: string;
  category: string | null;
  weight: number;
  matches: MoonMatch[];
}

export interface MoonAnalysis {
  overall_score: number;
  interpretation: string;
  hair_types: string[];
  ingredients_total: number;
  ingredients_categorized: number;
  coverage_pct: number;
  alerts: { name: string; category: string; hair_type: string; reason: string }[];
  benefits: { name: string; category: string; hair_type: string; reason: string }[];
  breakdown: MoonBreakdown[];
}

export async function analyzeWithMoon(inci: string[], hair_types: string[]): Promise<MoonAnalysis> {
  return fetchJSON<MoonAnalysis>('/moon/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ inci, hair_types }),
  });
}

// --- Hair profile (the questionnaire that feeds Moon) ---
export interface HairProfile {
  curl_type?: string | null;
  curl_subtype?: string | null;
  color?: string | null;
  volume?: string | null;
  thickness?: string | null;
  length?: string | null;
  scalp_oiliness?: string | null;
  dryness_damage?: string | null;
  chemical_treatments?: string[];
  heat_usage?: string | null;
  extensions?: string | null;
  wash_frequency?: string | null;
  sun_exposure?: string | null;
  water_exposure?: string | null;
  scalp_issues?: boolean | null;
}

export interface HairProfileSaved extends HairProfile {
  profile_id: string;
  user_id: string | null;
  derived_hair_types: string[];
}

export async function saveHairProfile(profile: HairProfile, user_id?: string): Promise<HairProfileSaved> {
  return fetchJSON<HairProfileSaved>('/moon/profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...profile, user_id }),
  });
}

export async function getHairProfile(user_id: string): Promise<HairProfileSaved> {
  return fetchJSON<HairProfileSaved>(`/moon/profile/${user_id}`);
}

// --- Moon chat ---
export interface MoonChatMessage { role: 'user' | 'assistant'; content: string; }

export interface MoonChatResponse {
  reply: string;
  profile_summary: string;
  hair_types: string[];
  analysis: MoonAnalysis | null;
  alternatives: { product_id: string; name: string; brand: string; score: number; interpretation: string }[];
}

export async function chatWithMoon(params: {
  messages: MoonChatMessage[];
  user_id?: string;
  profile?: HairProfile;
  product_id?: string;
  inci?: string[];
}): Promise<MoonChatResponse> {
  return fetchJSON<MoonChatResponse>('/moon/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
}
