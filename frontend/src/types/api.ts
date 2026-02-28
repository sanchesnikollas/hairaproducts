export interface BrandCoverage {
  id: number;
  brand_slug: string;
  discovered_total: number;
  hair_total: number;
  kits_total: number;
  non_hair_total: number;
  extracted_total: number;
  verified_inci_total: number;
  verified_inci_rate: number;
  catalog_only_total: number;
  quarantined_total: number;
  status: string;
  blueprint_version: number;
  coverage_report: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface ProductEvidence {
  id: number;
  field_name: string;
  source_url: string | null;
  evidence_locator: string | null;
  raw_source_text: string | null;
  extraction_method: string | null;
  extracted_at: string | null;
}

export interface QualityIssue {
  field: string;
  code: string;
  severity: 'error' | 'warning' | 'info';
  message: string;
  details: string;
}

export interface QualityReport {
  score: number;
  error_count: number;
  warning_count: number;
  issues: QualityIssue[];
}

export interface Product {
  id: string;
  brand_slug: string;
  product_name: string;
  product_url: string;
  image_url_main: string | null;
  product_type_normalized: string | null;
  gender_target: string | null;
  inci_ingredients: string[] | null;
  confidence: number;
  verification_status: string;
  product_labels: {
    detected: string[];
    inferred: string[];
    confidence: number;
    sources: string[];
    manually_verified: boolean;
    manually_overridden: boolean;
  } | null;
  extraction_method: string | null;
  description: string | null;
  usage_instructions: string | null;
  benefits_claims: string[] | null;
  size_volume: string | null;
  line_collection: string | null;
  price: number | null;
  currency: string | null;
  created_at: string;
  updated_at: string;
  is_kit?: boolean;
  evidence?: ProductEvidence[];
  quality?: QualityReport;
}

export interface QuarantineItem {
  id: string;
  product_id: string;
  brand_slug: string | null;
  product_name: string | null;
  product_url: string | null;
  rejection_reason: string;
  rejection_code: string | null;
  review_status: string;
  reviewer_notes: string | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
