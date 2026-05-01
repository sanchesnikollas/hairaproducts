export interface BrandQualityMetrics {
  avg_confidence: number;
  has_description_pct: number;
  has_image_pct: number;
  has_category_pct: number;
  has_labels_pct: number;
  avg_ingredients: number;
}

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
  last_run: string | null;
  blueprint_version: number;
  coverage_report: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  quality?: BrandQualityMetrics;
}

export interface ProductEvidence {
  id: number;
  field_name: string;
  source_url: string | null;
  evidence_locator: string | null;
  raw_source_text: string | null;
  extraction_method: string | null;
  source_section_label: string | null;
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
  product_category: string | null;
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
  composition: string | null;
  care_usage: string | null;
  benefits_claims: string[] | null;
  size_volume: string | null;
  line_collection: string | null;
  price: number | null;
  currency: string | null;
  created_at: string;
  updated_at: string;
  is_kit?: boolean;
  // Hair classification (added 2026-04-28)
  ph: number | null;
  hair_type: string[] | null;
  audience_age: string | null;
  function_objective: string | null;
  image_url_front: string | null;
  image_url_back: string | null;
  evidence?: ProductEvidence[];
  quality?: QualityReport;
}

export const HAIR_TYPES = [
  "liso", "ondulado", "cacheado", "crespo",
  "oleoso", "seco", "misto", "normal",
  "com_quimica", "tingido",
  "danificado", "sensibilizado", "fino", "grosso",
] as const;
export type HairType = (typeof HAIR_TYPES)[number];

export const AUDIENCE_AGES = ["under_3", "kids", "teen", "adult"] as const;
export type AudienceAge = (typeof AUDIENCE_AGES)[number];

export const FUNCTIONS = [
  "limpar", "condicionar", "hidratar", "nutrir", "reconstruir",
  "definir", "finalizar", "proteger", "tratar", "modelar",
  "esfoliar", "alisar", "ondular", "colorir",
] as const;
export type FunctionObjective = (typeof FUNCTIONS)[number];

export const HAIR_TYPE_LABELS: Record<string, string> = {
  liso: "Liso",
  ondulado: "Ondulado",
  cacheado: "Cacheado",
  crespo: "Crespo",
  oleoso: "Oleoso",
  seco: "Seco",
  misto: "Misto",
  normal: "Normal",
  com_quimica: "Com química",
  tingido: "Tingido",
  danificado: "Danificado",
  sensibilizado: "Sensibilizado",
  fino: "Fino",
  grosso: "Grosso",
};

export const AUDIENCE_AGE_LABELS: Record<string, string> = {
  under_3: "Bebê (<3 anos)",
  kids: "Infantil (3-11)",
  teen: "Adolescente (12-17)",
  adult: "Adulto (18+)",
};

export const FUNCTION_LABELS: Record<string, string> = {
  limpar: "Limpar",
  condicionar: "Condicionar",
  hidratar: "Hidratar",
  nutrir: "Nutrir",
  reconstruir: "Reconstruir",
  definir: "Definir",
  finalizar: "Finalizar",
  proteger: "Proteger",
  tratar: "Tratar",
  modelar: "Modelar",
  esfoliar: "Esfoliar",
  alisar: "Alisar",
  ondular: "Ondular",
  colorir: "Colorir",
};

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
  limit: number;
  offset: number;
  status_counts?: {
    all: number;
    verified_inci: number;
    catalog_only: number;
    quarantined: number;
  };
}

export interface IngredientSummary {
  id: string;
  canonical_name: string;
  inci_name: string | null;
  category: string | null;
  product_count: number;
}

export interface ProductIngredient {
  position: number;
  raw_name: string;
  validation_status: string;
  ingredient: {
    id: string;
    canonical_name: string;
    category: string | null;
  };
}

export interface ValidationComparison {
  id: string;
  field_name: string;
  pass_1_value: string | null;
  pass_2_value: string | null;
  resolution: string;
  created_at: string | null;
}

export interface ReviewQueueItem {
  id: string;
  product_id: string;
  field_name: string;
  status: string;
  reviewer_notes: string | null;
  created_at: string | null;
  product_name: string | null;
  brand_slug: string | null;
  comparison: {
    pass_1_value: string | null;
    pass_2_value: string | null;
    resolution: string;
  } | null;
}

export interface BrandSummary {
  brand_slug: string;
  brand_name: string;
  product_count: number;
  inci_rate: number;
  platform: string | null;
  is_active: boolean;
}

export interface GlobalStats {
  total_brands: number;
  total_products: number;
  avg_inci_rate: number;
  platforms: string[];
}
