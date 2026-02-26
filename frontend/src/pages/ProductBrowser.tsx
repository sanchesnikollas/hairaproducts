import { useState, useMemo, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { getProducts, getProduct } from '../lib/api';
import { useAPI } from '../hooks/useAPI';
import type { Product } from '../types/api';
import StatusBadge from '../components/StatusBadge';
import LoadingState, { ErrorState, EmptyState } from '../components/LoadingState';

const SEAL_DISPLAY: Record<string, string> = {
  sulfate_free: 'Sulfate Free',
  paraben_free: 'Paraben Free',
  silicone_free: 'Silicone Free',
  fragrance_free: 'Fragrance Free',
  vegan: 'Vegan',
  cruelty_free: 'Cruelty Free',
  organic: 'Organic',
  natural: 'Natural',
  hypoallergenic: 'Hypoallergenic',
  dermatologically_tested: 'Derm. Tested',
  ophthalmologically_tested: 'Ophth. Tested',
  uv_protection: 'UV Protection',
  thermal_protection: 'Thermal Protection',
  low_poo: 'Low Poo',
  no_poo: 'No Poo',
};

export default function ProductBrowser() {
  const [search, setSearch] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sealFilter, setSealFilter] = useState('');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  const fetcher = useCallback(
    () => getProducts({ brand: brandFilter || undefined, verified_only: verifiedOnly }),
    [brandFilter, verifiedOnly]
  );
  const { data: products, loading, error, refetch } = useAPI(fetcher, [brandFilter, verifiedOnly]);

  const filtered = useMemo(() => {
    if (!products) return [];
    let result = products;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.product_name.toLowerCase().includes(q) ||
          p.brand_slug.toLowerCase().includes(q) ||
          (p.product_type_normalized ?? '').toLowerCase().includes(q)
      );
    }
    if (sealFilter) {
      result = result.filter((p) => {
        if (!p.product_labels) return false;
        return p.product_labels.detected.includes(sealFilter) || p.product_labels.inferred.includes(sealFilter);
      });
    }
    return result;
  }, [products, search, sealFilter]);

  const brandSlugs = useMemo(() => {
    if (!products) return [];
    return [...new Set(products.map((p) => p.brand_slug))].sort();
  }, [products]);

  if (loading) return <LoadingState message="Loading products..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
          Product Browser
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          Browse and search verified hair products with INCI ingredient data.
        </p>
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.15 }}
        className="flex flex-wrap items-center gap-3"
      >
        {/* Search */}
        <div className="relative flex-1 min-w-[240px] max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search products..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all"
          />
        </div>

        {/* Brand select */}
        <select
          value={brandFilter}
          onChange={(e) => setBrandFilter(e.target.value)}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All brands</option>
          {brandSlugs.map((slug) => (
            <option key={slug} value={slug}>
              {slug}
            </option>
          ))}
        </select>

        {/* Verified toggle */}
        <button
          onClick={() => setVerifiedOnly(!verifiedOnly)}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all ${
            verifiedOnly
              ? 'bg-sage-bg border-sage/20 text-sage'
              : 'bg-white border-ink/8 text-ink-muted hover:text-ink hover:border-ink/15'
          }`}
        >
          <span className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-all ${
            verifiedOnly ? 'bg-sage border-sage' : 'border-ink/20'
          }`}>
            {verifiedOnly && (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </span>
          Verified INCI only
        </button>

        {/* Seal filter */}
        <select
          value={sealFilter}
          onChange={(e) => setSealFilter(e.target.value)}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All seals</option>
          {Object.entries(SEAL_DISPLAY).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        {/* Count */}
        <span className="text-xs text-ink-faint ml-auto tabular-nums">
          {filtered.length} product{filtered.length !== 1 ? 's' : ''}
        </span>
      </motion.div>

      {/* Product Grid */}
      {filtered.length === 0 ? (
        <EmptyState title="No products found" description="Try adjusting your search or filters." />
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
        >
          {filtered.map((product, i) => (
            <ProductCard
              key={product.id}
              product={product}
              index={i}
              onClick={() => setSelectedProductId(product.id)}
            />
          ))}
        </motion.div>
      )}

      {/* Product Detail Modal */}
      <AnimatePresence>
        {selectedProductId && (
          <ProductModal
            productId={selectedProductId}
            onClose={() => setSelectedProductId(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Product Card ──

function ProductCard({ product, index, onClick }: { product: Product; index: number; onClick: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.3) }}
      onClick={onClick}
      className="bg-white rounded-xl border border-ink/5 p-5 shadow-sm cursor-pointer hover:shadow-md hover:border-champagne/20 transition-all group"
    >
      <div className="flex gap-4">
        {/* Image */}
        <div className="w-16 h-16 rounded-lg bg-cream-dark flex-shrink-0 overflow-hidden">
          {product.image_url_main ? (
            <img
              src={product.image_url_main}
              alt={product.product_name}
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = 'none';
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-faint">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-medium text-ink truncate">{product.product_name}</h3>
          <p className="text-xs text-ink-muted mt-0.5">{product.brand_slug}</p>
          <div className="flex items-center gap-2 mt-2">
            <StatusBadge status={product.verification_status} />
            {product.product_type_normalized && (
              <span className="text-[11px] text-ink-faint">{product.product_type_normalized}</span>
            )}
          </div>
        </div>
      </div>

      {/* INCI preview */}
      {product.inci_ingredients && product.inci_ingredients.length > 0 && (
        <div className="mt-3 pt-3 border-t border-ink/5">
          <p className="text-[11px] text-ink-faint leading-relaxed line-clamp-2">
            {product.inci_ingredients.join(', ')}
          </p>
        </div>
      )}

      {/* Seal Badges */}
      {product.product_labels && (product.product_labels.detected.length > 0 || product.product_labels.inferred.length > 0) && (
        <div className="mt-3 pt-3 border-t border-ink/5 flex flex-wrap gap-1.5">
          {product.product_labels.detected.map(seal => (
            <span key={seal} className="inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-full bg-sage-bg text-sage border border-sage/10">
              {SEAL_DISPLAY[seal] || seal}
            </span>
          ))}
          {product.product_labels.inferred.map(seal => (
            <span key={seal} className="inline-flex items-center text-[10px] font-medium px-2 py-0.5 rounded-full bg-champagne/10 text-champagne-dark border border-champagne/10">
              {SEAL_DISPLAY[seal] || seal}
            </span>
          ))}
        </div>
      )}

      {/* Confidence */}
      <div className="mt-3 flex items-center justify-between">
        <span className="text-[10px] uppercase tracking-wider text-ink-faint">
          Confidence
        </span>
        <span className="text-xs font-medium tabular-nums text-ink-light">
          {Math.round(product.confidence * 100)}%
        </span>
      </div>
    </motion.div>
  );
}

// ── Product Detail Modal ──

function ProductModal({ productId, onClose }: { productId: string; onClose: () => void }) {
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    getProduct(productId)
      .then((result) => {
        if (!cancelled) {
          setProduct(result);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load product');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [productId]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-ink/30 backdrop-blur-sm z-50 flex items-center justify-center p-8"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.3 }}
        className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && (
          <div className="p-12 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-champagne/30 border-t-champagne rounded-full animate-spin" />
              <span className="text-sm text-ink-muted">Loading product details...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="p-12 flex items-center justify-center">
            <div className="text-center">
              <p className="text-sm text-coral">{error}</p>
              <button
                onClick={onClose}
                className="mt-3 text-sm text-ink-muted hover:text-ink transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        )}

        {product && (
          <>
            {/* Modal Header */}
            <div className="flex items-start justify-between p-6 border-b border-ink/5">
              <div className="flex gap-4">
                {product.image_url_main && (
                  <div className="w-20 h-20 rounded-xl bg-cream-dark overflow-hidden flex-shrink-0">
                    <img
                      src={product.image_url_main}
                      alt={product.product_name}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}
                <div>
                  <h2 className="font-display text-xl font-semibold text-ink">
                    {product.product_name}
                  </h2>
                  <p className="text-sm text-ink-muted mt-0.5">{product.brand_slug}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <StatusBadge status={product.verification_status} size="md" />
                    {product.product_type_normalized && (
                      <span className="text-xs text-ink-faint bg-ink/3 px-2 py-0.5 rounded-full">
                        {product.product_type_normalized}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <button
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-ink/5 transition-colors text-ink-muted"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-6">
              {/* Meta */}
              <div className="grid grid-cols-2 gap-4">
                <MetaField label="URL" value={product.product_url} isLink />
                <MetaField label="Confidence" value={`${Math.round(product.confidence * 100)}%`} />
                <MetaField label="Extraction Method" value={product.extraction_method ?? 'N/A'} />
                <MetaField label="Gender" value={product.gender_target ?? 'Unknown'} />
                {product.price && (
                  <MetaField label="Price" value={`${product.currency ?? ''} ${product.price}`} />
                )}
                {product.size_volume && (
                  <MetaField label="Size / Volume" value={product.size_volume} />
                )}
                {product.line_collection && (
                  <MetaField label="Line / Collection" value={product.line_collection} />
                )}
              </div>

              {/* Quality Seals */}
              {product.product_labels && (product.product_labels.detected.length > 0 || product.product_labels.inferred.length > 0) && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                    Quality Seals
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {product.product_labels.detected.map(seal => (
                      <span key={seal} className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-sage-bg text-sage border border-sage/15">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 12l2 2 4-4"/><circle cx="12" cy="12" r="10"/></svg>
                        {SEAL_DISPLAY[seal] || seal}
                      </span>
                    ))}
                    {product.product_labels.inferred.map(seal => (
                      <span key={seal} className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-champagne/10 text-champagne-dark border border-champagne/15">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2l2.4 7.4h7.6l-6 4.6 2.3 7-6.3-4.6-6.3 4.6 2.3-7-6-4.6h7.6z"/></svg>
                        {SEAL_DISPLAY[seal] || seal}
                      </span>
                    ))}
                  </div>
                  <p className="text-[10px] text-ink-faint mt-2">
                    <span className="text-sage">●</span> Detected from product text &nbsp; <span className="text-champagne-dark">●</span> Inferred from INCI analysis &nbsp; Confidence: {Math.round(product.product_labels.confidence * 100)}%
                  </p>
                </div>
              )}

              {/* Description */}
              {product.description && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Description</h3>
                  <p className="text-sm text-ink-light leading-relaxed">{product.description}</p>
                </div>
              )}

              {/* Usage Instructions */}
              {product.usage_instructions && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">Usage Instructions</h3>
                  <p className="text-sm text-ink-light leading-relaxed">{product.usage_instructions}</p>
                </div>
              )}

              {/* Benefits & Claims */}
              {product.benefits_claims && product.benefits_claims.length > 0 && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                    Benefits & Claims ({product.benefits_claims.length})
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {product.benefits_claims.map((claim, i) => (
                      <span key={i} className="text-xs text-ink-light bg-cream px-3 py-1 rounded-lg">
                        {claim}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* INCI List */}
              {product.inci_ingredients && product.inci_ingredients.length > 0 && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                    INCI Ingredients ({product.inci_ingredients.length})
                  </h3>
                  <div className="bg-cream rounded-xl p-4">
                    <p className="text-sm text-ink-light leading-relaxed">
                      {product.inci_ingredients.join(', ')}
                    </p>
                  </div>
                </div>
              )}

              {/* Evidence */}
              {product.evidence && product.evidence.length > 0 && (
                <div>
                  <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                    Evidence ({product.evidence.length})
                  </h3>
                  <div className="space-y-2">
                    {product.evidence.map((ev) => (
                      <div key={ev.id} className="flex items-start gap-3 p-3 bg-cream rounded-lg">
                        <div className="flex-1">
                          <span className="text-xs font-medium text-ink">{ev.field_name}</span>
                          <p className="text-xs text-ink-muted mt-0.5 break-all">{ev.value}</p>
                        </div>
                        <div className="text-right">
                          <span className="text-[10px] uppercase tracking-wider text-ink-faint">{ev.source}</span>
                          <p className="text-xs font-medium tabular-nums text-ink-light">
                            {Math.round(ev.confidence * 100)}%
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  );
}

function MetaField({ label, value, isLink }: { label: string; value: string; isLink?: boolean }) {
  return (
    <div>
      <span className="text-[10px] uppercase tracking-wider text-ink-faint">{label}</span>
      {isLink ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="block text-sm text-champagne-dark hover:underline truncate mt-0.5"
        >
          {value}
        </a>
      ) : (
        <p className="text-sm text-ink-light mt-0.5">{value}</p>
      )}
    </div>
  );
}
