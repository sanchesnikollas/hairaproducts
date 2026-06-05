import { useParams, Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import SealBadge from '@/components/SealBadge';
import LoadingState, { ErrorState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getBrandProduct, getProduct } from '@/lib/api';
import type { Product } from '@/types/api';

const FLAGGED_TERMS = [
  'dimethicone',
  'silicone',
  'siloxane',
  'sulfate',
  'sulphate',
  'lauryl',
  'laureth',
  'petrolatum',
  'paraben',
];

function isIngredientFlagged(ingredient: string): boolean {
  const lower = ingredient.toLowerCase();
  return FLAGGED_TERMS.some((term) => lower.includes(term));
}

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function statusColor(status: string): string {
  switch (status) {
    case 'verified_inci':
      return 'border-emerald-200 bg-emerald-50 text-emerald-700';
    case 'catalog_only':
      return 'border-amber-200 bg-amber-50 text-amber-700';
    case 'quarantined':
      return 'border-red-200 bg-red-50 text-red-700';
    default:
      return '';
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case 'verified_inci':
      return 'Verified INCI';
    case 'catalog_only':
      return 'Catalog Only';
    case 'quarantined':
      return 'Quarantined';
    default:
      return status;
  }
}

async function fetchProduct(slug: string, productId: string): Promise<Product> {
  try {
    return await getBrandProduct(slug, productId);
  } catch {
    return await getProduct(productId);
  }
}

export default function ProductDetail() {
  const { slug, productId } = useParams<{ slug: string; productId: string }>();

  const { data: product, loading, error } = useAPI(
    () => fetchProduct(slug!, productId!),
    [slug, productId]
  );

  if (loading) return <LoadingState message="Loading product..." />;
  if (error) return <ErrorState message={error} />;
  if (!product) return null;

  const allSeals = [
    ...(product.product_labels?.detected ?? []),
    ...(product.product_labels?.inferred ?? []),
  ];

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div className="flex items-center gap-2 text-sm text-ink-muted flex-wrap">
          <Link to="/ops" className="hover:text-ink transition-colors">Home</Link>
          <span>/</span>
          <Link to="/ops/brands" className="hover:text-ink transition-colors">Marcas</Link>
          <span>/</span>
          <Link to={`/ops/brands/${slug}`} className="hover:text-ink transition-colors">
            {formatBrandName(slug!)}
          </Link>
          <span>/</span>
          <span className="text-ink font-medium truncate max-w-xs">{product.product_name}</span>
        </div>
      </motion.div>

      {/* 2-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Left: Image */}
        <motion.div
          initial={{ opacity: 0, x: -16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="lg:col-span-2 lg:sticky lg:top-24 lg:self-start"
        >
          <Card className="overflow-hidden">
            <div className="aspect-square w-full bg-muted flex items-center justify-center">
              {product.image_url_main ? (
                <img
                  src={product.image_url_main}
                  alt={product.product_name}
                  className="w-full h-full object-contain"
                />
              ) : (
                <svg
                  className="w-16 h-16 text-muted-foreground/30"
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}
                >
                  <path
                    strokeLinecap="round" strokeLinejoin="round"
                    d="M3 7h18M3 7a2 2 0 00-2 2v9a2 2 0 002 2h18a2 2 0 002-2V9a2 2 0 00-2-2M3 7V5a2 2 0 012-2h3m9 0h3a2 2 0 012 2v2M9 3h6"
                  />
                </svg>
              )}
            </div>
          </Card>
        </motion.div>

        {/* Right: Data */}
        <motion.div
          initial={{ opacity: 0, x: 16 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.15 }}
          className="lg:col-span-3 space-y-6"
        >
          {/* Product Name & Status */}
          <div>
            <h1 className="font-display text-3xl font-semibold tracking-tight text-ink leading-tight">
              {product.product_name}
            </h1>
            <div className="flex items-center gap-3 mt-3 flex-wrap">
              <Link
                to={`/ops/brands/${slug}`}
                className="text-sm text-champagne-dark hover:underline font-medium"
              >
                {formatBrandName(slug!)}
              </Link>
              <Badge
                variant="outline"
                className={statusColor(product.verification_status)}
              >
                {statusLabel(product.verification_status)}
              </Badge>
              {product.product_category && (
                <Badge variant="outline" className="text-xs">
                  {product.product_category.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </Badge>
              )}
            </div>
            {product.size_volume && (
              <p className="text-sm text-ink-muted mt-2">{product.size_volume}</p>
            )}
            {product.price != null && (
              <p className="text-lg font-semibold text-ink mt-1">
                {product.currency ?? 'R$'} {product.price.toFixed(2)}
              </p>
            )}
          </div>

          {/* Seals */}
          {allSeals.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <h2 className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-3">
                  Quality Seals
                </h2>
                <div className="flex flex-wrap gap-2">
                  {allSeals.map((seal) => (
                    <SealBadge key={seal} seal={seal} />
                  ))}
                </div>
                {product.product_labels && (
                  <p className="text-xs text-muted-foreground mt-3">
                    Confidence: {Math.round(product.product_labels.confidence * 100)}%
                    {product.product_labels.manually_verified && ' (manually verified)'}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* INCI Ingredients */}
          {product.inci_ingredients && product.inci_ingredients.length > 0 && (
            <Card>
              <CardContent className="pt-4">
                <h2 className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-3">
                  INCI Ingredients ({product.inci_ingredients.length})
                </h2>
                <ol className="space-y-1">
                  {product.inci_ingredients.map((ingredient, i) => {
                    const flagged = isIngredientFlagged(ingredient);
                    return (
                      <li
                        key={i}
                        className={`text-sm flex items-start gap-2 py-0.5 ${
                          flagged ? 'text-amber-700' : 'text-ink-light'
                        }`}
                      >
                        <span className="text-xs text-muted-foreground tabular-nums w-6 text-right flex-shrink-0 mt-0.5">
                          {i + 1}.
                        </span>
                        <span className={flagged ? 'font-medium bg-amber-50 px-1 rounded' : ''}>
                          {ingredient}
                        </span>
                      </li>
                    );
                  })}
                </ol>
              </CardContent>
            </Card>
          )}

          {/* Expandable Sections */}
          {product.composition && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-ink hover:text-champagne-dark transition-colors py-2 border-b border-ink/5">
                Composicao
              </summary>
              <div className="pt-3 pb-2 text-sm text-ink-light whitespace-pre-wrap">
                {product.composition}
              </div>
            </details>
          )}

          {(product.usage_instructions || product.care_usage) && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-ink hover:text-champagne-dark transition-colors py-2 border-b border-ink/5">
                Modo de Uso
              </summary>
              <div className="pt-3 pb-2 text-sm text-ink-light whitespace-pre-wrap">
                {product.usage_instructions || product.care_usage}
              </div>
            </details>
          )}

          {product.description && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-ink hover:text-champagne-dark transition-colors py-2 border-b border-ink/5">
                Descricao
              </summary>
              <div className="pt-3 pb-2 text-sm text-ink-light whitespace-pre-wrap">
                {product.description}
              </div>
            </details>
          )}

          {product.benefits_claims && product.benefits_claims.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-ink hover:text-champagne-dark transition-colors py-2 border-b border-ink/5">
                Benefits & Claims
              </summary>
              <ul className="pt-3 pb-2 space-y-1">
                {product.benefits_claims.map((claim, i) => (
                  <li key={i} className="text-sm text-ink-light flex items-start gap-2">
                    <span className="text-muted-foreground mt-1">-</span>
                    {claim}
                  </li>
                ))}
              </ul>
            </details>
          )}

          {/* Evidence Trail */}
          {product.evidence && product.evidence.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-sm font-medium text-ink hover:text-champagne-dark transition-colors py-2 border-b border-ink/5">
                Evidence Trail ({product.evidence.length} records)
              </summary>
              <div className="pt-3 pb-2 space-y-3">
                {product.evidence.map((ev) => (
                  <div key={ev.id} className="rounded-lg border border-ink/5 p-3 text-xs space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-ink">{ev.field_name}</span>
                      {ev.extraction_method && (
                        <Badge variant="outline" className="text-[10px] h-auto px-1.5 py-0">
                          {ev.extraction_method}
                        </Badge>
                      )}
                    </div>
                    {ev.evidence_locator && (
                      <p className="text-muted-foreground font-mono truncate">
                        {ev.evidence_locator}
                      </p>
                    )}
                    {ev.extracted_at && (
                      <p className="text-muted-foreground">
                        {new Date(ev.extracted_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </details>
          )}

          {/* External Link */}
          {product.product_url && (
            <div className="pt-2">
              <a
                href={product.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-champagne-dark hover:underline inline-flex items-center gap-1"
              >
                View on store
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6" />
                  <polyline points="15 3 21 3 21 9" />
                  <line x1="10" y1="14" x2="21" y2="3" />
                </svg>
              </a>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
