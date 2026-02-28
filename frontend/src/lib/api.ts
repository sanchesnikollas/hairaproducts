import type { BrandCoverage, PaginatedResponse, Product, QuarantineItem } from '../types/api';

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

// ── Config ──

export async function getFocusBrand(): Promise<{ focus_brand: string | null }> {
  return fetchJSON<{ focus_brand: string | null }>('/config/focus-brand');
}

// ── Quarantine ──

export async function getQuarantine(reviewStatus?: string): Promise<QuarantineItem[]> {
  const qs = reviewStatus ? `?review_status=${reviewStatus}` : '';
  return fetchJSON<QuarantineItem[]>(`/quarantine${qs}`);
}

export async function approveQuarantine(id: string): Promise<{ status: string; quarantine_id: string }> {
  return fetchJSON(`/quarantine/${id}/approve`, { method: 'POST' });
}

export async function rejectQuarantine(id: string, notes?: string): Promise<{ status: string; quarantine_id: string }> {
  const params = notes ? `?notes=${encodeURIComponent(notes)}` : '';
  return fetchJSON(`/quarantine/${id}/reject${params}`, { method: 'POST' });
}
