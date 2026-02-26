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
  value: string;
  source: string;
  confidence: number;
  selector_used: string | null;
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
  price: string | null;
  currency: string | null;
  created_at: string;
  updated_at: string;
  evidence?: ProductEvidence[];
}

export interface QuarantineItem {
  id: number;
  product_id: number;
  brand_slug: string;
  product_name: string;
  product_url: string;
  reason: string;
  failed_checks: string;
  review_status: string;
  reviewed_at: string | null;
  product: Product;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}
