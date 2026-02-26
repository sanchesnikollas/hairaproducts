import type { BrandCoverage, Product, QuarantineItem } from '../types/api';

const BASE_URL = '/api';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
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
  page?: number;
  per_page?: number;
}

export async function getProducts(filters: ProductFilters = {}): Promise<Product[]> {
  const params = new URLSearchParams();
  if (filters.brand) params.set('brand_slug', filters.brand);
  if (filters.verified_only !== undefined) params.set('verified_only', String(filters.verified_only));
  if (filters.per_page) params.set('limit', String(filters.per_page));
  if (filters.page) params.set('offset', String(((filters.page ?? 1) - 1) * (filters.per_page ?? 100)));
  const qs = params.toString();
  return fetchJSON<Product[]>(`/products${qs ? `?${qs}` : ''}`);
}

export async function getProduct(id: string): Promise<Product> {
  return fetchJSON<Product>(`/products/${id}`);
}

// ── Quarantine ──

export async function getQuarantine(reviewStatus?: string): Promise<QuarantineItem[]> {
  const qs = reviewStatus ? `?review_status=${reviewStatus}` : '';
  return fetchJSON<QuarantineItem[]>(`/quarantine${qs}`);
}

export async function approveQuarantine(id: number): Promise<QuarantineItem> {
  return fetchJSON<QuarantineItem>(`/quarantine/${id}/approve`, { method: 'POST' });
}
