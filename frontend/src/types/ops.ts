export interface OpsUser {
  id: string;
  name: string;
  email: string;
  role: "admin" | "reviewer";
}

export interface LoginResponse {
  token: string;
  user: OpsUser;
}

export interface DashboardKPIs {
  total_products: number;
  inci_coverage: number;
  pending_review: number;
  quarantined: number;
  published: number;
  avg_confidence: number;
  category_pct?: number;
  description_pct?: number;
  image_pct?: number;
  volume_pct?: number;
}

export interface DashboardData {
  kpis: DashboardKPIs;
  low_confidence: LowConfidenceProduct[];
  recent_activity: RevisionEntry[];
}

export interface LowConfidenceProduct {
  id: string;
  product_name: string;
  brand_slug: string;
  confidence: number;
  status_editorial: string | null;
}

export interface RevisionEntry {
  revision_id: string;
  entity_type: string;
  entity_id: string;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_by: string | null;
  change_source: string;
  change_reason: string | null;
  created_at: string;
}

export interface ReviewQueueItem {
  id: string;
  product_name: string;
  brand_slug: string;
  status_editorial: string | null;
  confidence: number;
  verification_status: string;
  assigned_to: string | null;
  created_at: string | null;
}

export interface ReviewQueueResponse {
  items: ReviewQueueItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface IngredientGaps {
  uncategorized: { id: string; canonical_name: string; inci_name: string | null }[];
  orphan_raw_names: { raw_name: string; product_count: number }[];
}
