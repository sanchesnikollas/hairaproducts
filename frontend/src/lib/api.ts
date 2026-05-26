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

export interface MoonAiAnalysis {
  summary: string;
  synergies: string[];
  personalized_alerts: string[];
  recommendation: string;
  _model?: string;
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
  ai_analysis: MoonAiAnalysis | null;
}

export interface MoonAnalyzeRequest {
  inci?: string[];
  product_id?: string;
  hair_types: string[];
  use_ai?: boolean;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('haira_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function analyzeWithMoon(req: MoonAnalyzeRequest): Promise<MoonAnalysis> {
  return fetchJSON<MoonAnalysis>('/moon/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(req),
  });
}

// ── Moon hair profile (perfil capilar salvo do usuário) ──

export interface MoonProfile {
  hair_types: string[];
  notes: string | null;
  exists: boolean;
}

export async function getMoonProfile(): Promise<MoonProfile> {
  return fetchJSON<MoonProfile>('/moon/profile', { headers: { ...authHeaders() } });
}

export async function saveMoonProfile(hair_types: string[], notes?: string): Promise<MoonProfile> {
  return fetchJSON<MoonProfile>('/moon/profile', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ hair_types, notes: notes ?? null }),
  });
}
