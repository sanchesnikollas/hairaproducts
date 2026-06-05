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

export interface InciSummaryBrand {
  brand_slug: string;
  total: number;
  pending: number;
  verified: number;
  pct: number;
}

export async function opsGetInciSummary(): Promise<{
  brands: InciSummaryBrand[];
  total_pending: number;
}> {
  const res = await authFetch(`${BASE}/ops/inci-summary`);
  return res.json();
}

export async function opsListProducts(params?: { brand?: string; status_editorial?: string; search?: string; page?: number; verification_status?: string; per_page?: number; gap?: string }): Promise<{
  items: {
    id: string; product_name: string; brand_slug: string;
    verification_status: string; status_operacional: string | null;
    status_editorial: string | null; status_publicacao: string | null;
    confidence: number; assigned_to: string | null;
    data_quality?: DataQuality;
    image_url_main?: string;
    product_category?: string;
  }[];
  total: number; page: number; per_page: number;
}> {
  const qs = new URLSearchParams();
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.status_editorial) qs.set("status_editorial", params.status_editorial);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.verification_status) qs.set("verification_status", params.verification_status);
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  if (params?.gap) qs.set("gap", params.gap);
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

// ── Knowledge base (Doutoras' proprietary content) ──
export interface KnowledgeChunkSummary {
  source: string;
  char_count: number;
  token_estimate: number;
  updated_at: string | null;
}
export interface KnowledgeList {
  chunks: KnowledgeChunkSummary[];
  total_sources: number;
  total_chars: number;
  total_tokens_estimate: number;
}

export async function listKnowledge(): Promise<KnowledgeList> {
  return (await authFetch(`${BASE}/admin/knowledge`)).json();
}

export async function readKnowledge(source: string): Promise<KnowledgeChunkSummary & { content: string }> {
  return (await authFetch(`${BASE}/admin/knowledge/${encodeURIComponent(source)}`)).json();
}

export async function uploadKnowledge(file: File): Promise<{ action: 'created' | 'updated' } & KnowledgeChunkSummary> {
  const form = new FormData();
  form.append('file', file);
  // can't use authFetch because it forces JSON content-type
  const token = localStorage.getItem('haira_token');
  const res = await fetch(`${BASE}/admin/knowledge/upload`, {
    method: 'POST', body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }
  return res.json();
}

export async function deleteKnowledge(source: string): Promise<{ deleted: string }> {
  return (await authFetch(`${BASE}/admin/knowledge/${encodeURIComponent(source)}`, { method: 'DELETE' })).json();
}

// Moon personality config (DB-backed, editável via UI) ────────────────────────

export interface MoonConfigItem {
  key: string;
  value: string;
  description: string | null;
  updated_at: string | null;
  updated_by: string | null;
  char_count: number;
  token_estimate: number;
}

export interface MoonConfigList {
  config: MoonConfigItem[];
  total_keys: number;
}

export async function listMoonConfig(): Promise<MoonConfigList> {
  return (await authFetch(`${BASE}/admin/moon/config`)).json();
}

export async function getMoonConfigKey(key: string): Promise<MoonConfigItem> {
  return (await authFetch(`${BASE}/admin/moon/config/${encodeURIComponent(key)}`)).json();
}

export async function updateMoonConfigKey(key: string, value: string): Promise<MoonConfigItem> {
  return (await authFetch(`${BASE}/admin/moon/config/${encodeURIComponent(key)}`, {
    method: 'PUT', body: JSON.stringify({ value }),
  })).json();
}

export async function resetMoonConfigKey(key: string): Promise<MoonConfigItem> {
  return (await authFetch(`${BASE}/admin/moon/config/${encodeURIComponent(key)}/reset`, {
    method: 'POST',
  })).json();
}

// Moon metrics (admin) — wraps existing /moon/feedback/summary ─────────────────

export interface MoonFeedbackSummary {
  total: number;
  up: number;
  down: number;
  useful_pct: number | null;
  recent_downvotes: Array<{
    feedback_id: string;
    user_message: string | null;
    message_content: string;
    comment: string | null;
    profile: Record<string, unknown> | null;
    created_at: string;
  }>;
}

export async function getMoonFeedbackSummary(): Promise<MoonFeedbackSummary> {
  return (await authFetch(`${BASE}/moon/feedback/summary`)).json();
}

// Audit log viewer (admin) — wraps /api/admin/audit/* ─────────────────────────

export interface AuditSummary {
  auth: { total: number; login_ok: number; login_fail: number; fail_rate_pct: number | null };
  admin_actions: { total: number; top: Array<{ action: string; count: number }> };
  kb_retrievals: { total: number; by_intent: Record<string, number> };
}

export interface AuthEvent {
  event_id: string;
  event_type: string;
  email: string | null;
  user_id: string | null;
  ip_address: string | null;
  user_agent: string;
  detail: string | null;
  created_at: string | null;
}

export interface AdminActionEvent {
  action_id: string;
  actor_id: string;
  actor_email: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  before: unknown;
  after: unknown;
  ip_address: string | null;
  created_at: string | null;
}

export interface KbRetrievalEvent {
  log_id: string;
  user_id: string | null;
  conversation_id: string | null;
  query_hash: string;
  intent: string | null;
  kb_sources: string[];
  chunk_count: string | null;
  anthropic_tokens_in: string | null;
  anthropic_tokens_out: string | null;
  latency_ms: string | null;
  created_at: string | null;
}

export async function getAuditSummary(): Promise<AuditSummary> {
  return (await authFetch(`${BASE}/admin/audit/summary`)).json();
}

export async function listAuthEvents(limit = 100): Promise<{ events: AuthEvent[]; count: number }> {
  return (await authFetch(`${BASE}/admin/audit/auth-events?limit=${limit}`)).json();
}

export async function listAdminActions(limit = 100): Promise<{ actions: AdminActionEvent[]; count: number }> {
  return (await authFetch(`${BASE}/admin/audit/admin-actions?limit=${limit}`)).json();
}

export async function listKbRetrievals(limit = 100): Promise<{ retrievals: KbRetrievalEvent[]; count: number }> {
  return (await authFetch(`${BASE}/admin/audit/kb-retrievals?limit=${limit}`)).json();
}

// Brand registry CRUD (admin) ─────────────────────────────────────────────────

export interface BrandRegistryItem {
  brand_slug: string;
  brand_name: string;
  official_url_root: string | null;
  country: string | null;
  priority: number | null;
  status: string;
  platform: string | null;
  notes: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BrandCreatePayload {
  brand_name: string;
  brand_slug?: string;
  official_url_root?: string;
  country?: 'Brasil' | 'Internacional' | 'Outros';
  priority?: number;
  status?: 'active' | 'blocked' | 'blocked_maintenance' | 'out_of_scope';
  platform?: string;
  notes?: string;
}

export type BrandUpdatePayload = Partial<BrandCreatePayload>;

export async function listBrandRegistry(): Promise<{ brands: BrandRegistryItem[]; total: number }> {
  return (await authFetch(`${BASE}/admin/brands/registry`)).json();
}

export async function createBrand(data: BrandCreatePayload): Promise<BrandRegistryItem> {
  return (await authFetch(`${BASE}/admin/brands/registry`, {
    method: 'POST', body: JSON.stringify(data),
  })).json();
}

export async function updateBrand(slug: string, data: BrandUpdatePayload): Promise<BrandRegistryItem> {
  return (await authFetch(`${BASE}/admin/brands/registry/${encodeURIComponent(slug)}`, {
    method: 'PATCH', body: JSON.stringify(data),
  })).json();
}

export async function deleteBrand(slug: string): Promise<void> {
  await authFetch(`${BASE}/admin/brands/registry/${encodeURIComponent(slug)}`, { method: 'DELETE' });
}
