import type {
  LoginResponse, OpsUser, DashboardData, ReviewQueueResponse,
  RevisionEntry, IngredientGaps,
} from "../types/ops";

const BASE = "/api";

function getToken(): string | null {
  return localStorage.getItem("haira_token");
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    localStorage.removeItem("haira_token");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res;
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  return res.json();
}

export async function getMe(): Promise<OpsUser> {
  const res = await authFetch(`${BASE}/auth/me`);
  return res.json();
}

export async function createUser(data: { email: string; password: string; name: string; role: string }): Promise<OpsUser> {
  const res = await authFetch(`${BASE}/auth/users`, { method: "POST", body: JSON.stringify(data) });
  return res.json();
}

export async function getDashboard(): Promise<DashboardData> {
  const res = await authFetch(`${BASE}/ops/dashboard`);
  return res.json();
}

export interface DataQuality {
  fields: Record<string, boolean>;
  filled: number;
  total: number;
  pct: number;
}

export async function opsListProducts(params?: { brand?: string; status_editorial?: string; search?: string; page?: number }): Promise<{
  items: {
    id: string; product_name: string; brand_slug: string;
    verification_status: string; status_operacional: string | null;
    status_editorial: string | null; status_publicacao: string | null;
    confidence: number; assigned_to: string | null;
    data_quality?: DataQuality;
  }[];
  total: number; page: number; per_page: number;
}> {
  const qs = new URLSearchParams();
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.status_editorial) qs.set("status_editorial", params.status_editorial);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  const res = await authFetch(`${BASE}/ops/products?${qs}`);
  return res.json();
}

export async function opsGetProduct(id: string): Promise<{
  id: string; product_name: string; brand_slug: string;
  description: string | null; usage_instructions: string | null;
  product_category: string | null; verification_status: string;
  inci_ingredients: string[] | null; image_url_main: string | null;
  status_operacional: string | null; status_editorial: string | null;
  status_publicacao: string | null; confidence: number;
  confidence_factors: Record<string, unknown> | null;
  interpretation_data: Record<string, unknown> | null;
  application_data: Record<string, unknown> | null;
  decision_data: Record<string, unknown> | null;
  assigned_to: string | null;
  composition: string | null;
  extraction_method: string | null;
  product_url: string | null;
  size_volume: string | null;
  price: number | null;
  data_quality?: DataQuality;
}> {
  const res = await authFetch(`${BASE}/ops/products/${id}`);
  return res.json();
}

export async function opsUpdateProduct(id: string, data: Record<string, unknown>): Promise<void> {
  await authFetch(`${BASE}/ops/products/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function opsCreateProduct(data: {
  brand_slug: string; product_name: string; product_url?: string;
  description?: string; usage_instructions?: string; composition?: string;
  inci_ingredients?: string[]; product_category?: string;
  image_url_main?: string; size_volume?: string; price?: number;
}): Promise<{ product_id: string }> {
  const res = await authFetch(`${BASE}/ops/products`, { method: "POST", body: JSON.stringify(data) });
  return res.json();
}

export async function getUsers(): Promise<(OpsUser & { is_active?: boolean })[]> {
  const res = await authFetch(`${BASE}/auth/users`);
  return res.json();
}

export async function opsBatchUpdate(productIds: string[], updates: Record<string, string>): Promise<void> {
  await authFetch(`${BASE}/ops/products/batch`, {
    method: "PATCH",
    body: JSON.stringify({ product_ids: productIds, ...updates }),
  });
}

export async function getProductHistory(id: string): Promise<{ revisions: RevisionEntry[] }> {
  const res = await authFetch(`${BASE}/ops/products/${id}/history`);
  return res.json();
}

export async function getReviewQueue(params?: { type?: string; brand?: string; page?: number }): Promise<ReviewQueueResponse> {
  const qs = new URLSearchParams();
  if (params?.type) qs.set("type", params.type);
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.page) qs.set("page", String(params.page));
  const res = await authFetch(`${BASE}/ops/review-queue?${qs}`);
  return res.json();
}

export async function startReview(productId: string): Promise<void> {
  await authFetch(`${BASE}/ops/review-queue/${productId}/start`, { method: "POST" });
}

export async function resolveReview(productId: string, decision: string, notes?: string): Promise<void> {
  await authFetch(`${BASE}/ops/review-queue/${productId}/resolve`, {
    method: "POST",
    body: JSON.stringify({ decision, notes }),
  });
}

export async function opsUpdateIngredient(id: string, data: Record<string, unknown>): Promise<void> {
  await authFetch(`${BASE}/ops/ingredients/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function getIngredientGaps(): Promise<IngredientGaps> {
  const res = await authFetch(`${BASE}/ops/ingredients/gaps`);
  return res.json();
}
