import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import { getProducts, getProduct, getFocusBrand, updateProduct, getExportUrl } from '../lib/api';
import { useAPI } from '../hooks/useAPI';
import type { Product, ProductEvidence } from '../types/api';
import StatusBadge from '../components/StatusBadge';
import LoadingState, { ErrorState, EmptyState } from '../components/LoadingState';

// ── Seal Display Config ──

const SEAL_DISPLAY: Record<string, { label: string; icon: string }> = {
  sulfate_free: { label: 'Sulfate Free', icon: '🧪' },
  paraben_free: { label: 'Paraben Free', icon: '🛡' },
  silicone_free: { label: 'Silicone Free', icon: '💧' },
  fragrance_free: { label: 'Fragrance Free', icon: '🌸' },
  petrolatum_free: { label: 'Petrolatum Free', icon: '🧴' },
  dye_free: { label: 'Dye Free', icon: '🎨' },
  vegan: { label: 'Vegan', icon: '🌱' },
  cruelty_free: { label: 'Cruelty Free', icon: '🐰' },
  organic: { label: 'Organic', icon: '🌿' },
  natural: { label: 'Natural', icon: '🍃' },
  hypoallergenic: { label: 'Hypoallergenic', icon: '✨' },
  dermatologically_tested: { label: 'Derm. Tested', icon: '🔬' },
  ophthalmologically_tested: { label: 'Ophth. Tested', icon: '👁' },
  uv_protection: { label: 'UV Protection', icon: '☀️' },
  thermal_protection: { label: 'Thermal Protection', icon: '🔥' },
  low_poo: { label: 'Low Poo', icon: '💆' },
  no_poo: { label: 'No Poo', icon: '💆' },
};

const SEAL_FILTER_OPTIONS = Object.entries(SEAL_DISPLAY).map(([key, { label }]) => ({ key, label }));

function cleanProductName(name: string): string {
  return sanitizeText(name);
}

/**
 * Decode HTML entities, strip tags, normalize whitespace.
 * Uses the browser's DOMParser so we handle all entities correctly.
 */
function sanitizeText(text: string): string {
  if (!text) return text;
  const doc = new DOMParser().parseFromString(text, 'text/html');
  return (doc.body.textContent ?? '').replace(/\s+/g, ' ').trim();
}

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

// ── Main Component ──

const PER_PAGE = 100;

export default function ProductBrowser() {
  const [searchParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [brandFilter, setBrandFilter] = useState(searchParams.get('brand') ?? '');
  const [focusBrand, setFocusBrand] = useState<string | null>(null);
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sealFilter, setSealFilter] = useState('');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [qualityFilter, setQualityFilter] = useState<'' | 'errors' | 'warnings' | 'clean'>('');
  const [excludeKits, setExcludeKits] = useState(true);
  const [fieldFilter, setFieldFilter] = useState<'' | 'has_inci' | 'no_inci' | 'has_desc' | 'no_desc' | 'has_price' | 'no_price'>('');
  const [confidenceFilter, setConfidenceFilter] = useState<'' | 'high' | 'medium' | 'low'>('');
  const [page, setPage] = useState(1);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounce search to avoid hitting API on every keystroke
  useEffect(() => {
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  useEffect(() => {
    getFocusBrand()
      .then(({ focus_brand }) => {
        if (focus_brand) setFocusBrand(focus_brand);
      })
      .catch(() => {});
  }, []);

  const fetcher = useCallback(
    () => getProducts({
      brand: brandFilter || undefined,
      verified_only: verifiedOnly,
      exclude_kits: excludeKits,
      search: debouncedSearch || undefined,
      page,
      per_page: PER_PAGE,
    }),
    [brandFilter, verifiedOnly, excludeKits, debouncedSearch, page]
  );
  const { data: response, loading, error, refetch } = useAPI(fetcher, [brandFilter, verifiedOnly, excludeKits, debouncedSearch, page]);

  const products = response?.items ?? [];
  const totalProducts = response?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalProducts / PER_PAGE));

  const filtered = useMemo(() => {
    let result = products;
    if (sealFilter) {
      result = result.filter((p) => {
        const labels = p.product_labels;
        if (!labels) return false;
        return (labels.detected ?? []).includes(sealFilter) || (labels.inferred ?? []).includes(sealFilter);
      });
    }
    if (qualityFilter === 'errors') {
      result = result.filter((p) => (p.quality?.error_count ?? 0) > 0);
    } else if (qualityFilter === 'warnings') {
      result = result.filter((p) => (p.quality?.warning_count ?? 0) > 0 && (p.quality?.error_count ?? 0) === 0);
    } else if (qualityFilter === 'clean') {
      result = result.filter((p) => (p.quality?.error_count ?? 0) === 0 && (p.quality?.warning_count ?? 0) === 0);
    }
    if (fieldFilter === 'has_inci') result = result.filter((p) => (p.inci_ingredients?.length ?? 0) > 0);
    else if (fieldFilter === 'no_inci') result = result.filter((p) => !p.inci_ingredients?.length);
    else if (fieldFilter === 'has_desc') result = result.filter((p) => !!p.description?.trim());
    else if (fieldFilter === 'no_desc') result = result.filter((p) => !p.description?.trim());
    else if (fieldFilter === 'has_price') result = result.filter((p) => !!p.price);
    else if (fieldFilter === 'no_price') result = result.filter((p) => !p.price);
    if (confidenceFilter === 'high') result = result.filter((p) => p.confidence >= 0.8);
    else if (confidenceFilter === 'medium') result = result.filter((p) => p.confidence >= 0.5 && p.confidence < 0.8);
    else if (confidenceFilter === 'low') result = result.filter((p) => p.confidence < 0.5);
    return result;
  }, [products, sealFilter, qualityFilter, fieldFilter, confidenceFilter]);

  const brandSlugs = useMemo(() => {
    return [...new Set(products.map((p) => p.brand_slug))].sort();
  }, [products]);

  const statusCounts = useMemo(() => {
    const all = products;
    const verified = all.filter((p) => p.verification_status === 'verified_inci').length;
    const catalog = all.filter((p) => p.verification_status === 'catalog_only').length;
    const quarantined = all.filter((p) => p.verification_status === 'quarantined').length;
    const withErrors = all.filter((p) => (p.quality?.error_count ?? 0) > 0).length;
    const withWarnings = all.filter((p) => (p.quality?.warning_count ?? 0) > 0 && (p.quality?.error_count ?? 0) === 0).length;
    const clean = all.filter((p) => (p.quality?.error_count ?? 0) === 0 && (p.quality?.warning_count ?? 0) === 0).length;
    const hasInci = all.filter((p) => (p.inci_ingredients?.length ?? 0) > 0).length;
    const hasDesc = all.filter((p) => !!p.description?.trim()).length;
    const hasPrice = all.filter((p) => !!p.price).length;
    return { total: totalProducts, filtered: filtered.length, verified, catalog, quarantined, withErrors, withWarnings, clean, hasInci, hasDesc, hasPrice };
  }, [products, filtered, totalProducts]);

  if (loading) return <LoadingState message="Loading products..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">Products</h1>
            {focusBrand && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-champagne/10 text-champagne-dark border border-champagne/15">
                <span className="w-1.5 h-1.5 rounded-full bg-champagne" />
                {formatBrandName(focusBrand)}
              </span>
            )}
          </div>
          <div className="flex items-center gap-3">
          {/* Export */}
          <a
            href={getExportUrl({ brand: brandFilter || undefined, verified_only: verifiedOnly, search: debouncedSearch || undefined })}
            download
            className="flex items-center gap-1.5 px-3 py-2 bg-white border border-ink/8 rounded-lg text-xs font-medium text-ink-muted hover:text-ink hover:border-ink/15 transition-all"
            title="Export as CSV"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="7 10 12 15 17 10" />
              <line x1="12" y1="15" x2="12" y2="3" />
            </svg>
            Export CSV
          </a>
          {/* View Toggle */}
          <div className="flex items-center gap-1 bg-ink/3 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all ${viewMode === 'list' ? 'bg-white shadow-sm text-ink' : 'text-ink-faint hover:text-ink-muted'}`}
              title="List view"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
                <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
              </svg>
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-all ${viewMode === 'grid' ? 'bg-white shadow-sm text-ink' : 'text-ink-faint hover:text-ink-muted'}`}
              title="Grid view"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
                <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
              </svg>
            </button>
          </div>
          </div>
        </div>

        {/* Status Counts */}
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <span className="text-2xl font-display font-semibold text-ink tabular-nums">{statusCounts.total}</span>
          <span className="text-sm text-ink-muted">products</span>
          {statusCounts.filtered !== statusCounts.total && (
            <>
              <span className="w-px h-5 bg-ink/10" />
              <span className="text-sm text-ink-muted tabular-nums">{statusCounts.filtered} shown</span>
            </>
          )}
          <span className="w-px h-5 bg-ink/10" />
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-sage">
            <span className="w-2 h-2 rounded-full bg-sage" />
            {statusCounts.verified} verified
          </span>
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-amber">
            <span className="w-2 h-2 rounded-full bg-amber" />
            {statusCounts.catalog} catalog only
          </span>
          {statusCounts.quarantined > 0 && (
            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-coral">
              <span className="w-2 h-2 rounded-full bg-coral" />
              {statusCounts.quarantined} quarantined
            </span>
          )}
        </div>

        {/* Quality Filter Bar */}
        <div className="mt-3 flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-wider text-ink-faint font-semibold mr-1">Quality:</span>
          {([
            { key: '' as const, label: 'All', count: statusCounts.total },
            { key: 'errors' as const, label: 'Has Errors', count: statusCounts.withErrors },
            { key: 'warnings' as const, label: 'Warnings', count: statusCounts.withWarnings },
            { key: 'clean' as const, label: 'Clean', count: statusCounts.clean },
          ] as const).map(({ key, label, count }) => (
            <button
              key={key}
              onClick={() => setQualityFilter(key)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                qualityFilter === key
                  ? key === 'errors' ? 'bg-coral/10 text-coral border border-coral/20'
                    : key === 'warnings' ? 'bg-amber/10 text-amber border border-amber/20'
                    : key === 'clean' ? 'bg-sage/10 text-sage border border-sage/20'
                    : 'bg-champagne/10 text-champagne-dark border border-champagne/20'
                  : 'bg-ink/3 text-ink-muted hover:bg-ink/5 border border-transparent'
              }`}
            >
              {label}
              <span className="tabular-nums opacity-70">{count}</span>
            </button>
          ))}
        </div>
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.15 }}
        className="flex flex-wrap items-center gap-3"
      >
        <div className="relative flex-1 min-w-[240px] max-w-sm">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search by name, brand, or type..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all"
          />
        </div>

        <select
          value={brandFilter}
          onChange={(e) => { setBrandFilter(e.target.value); setPage(1); }}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All brands</option>
          {brandSlugs.map((slug) => (
            <option key={slug} value={slug}>
              {formatBrandName(slug)}
            </option>
          ))}
        </select>

        <select
          value={fieldFilter}
          onChange={(e) => setFieldFilter(e.target.value as typeof fieldFilter)}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All fields</option>
          <option value="has_inci">Has INCI ({statusCounts.hasInci})</option>
          <option value="no_inci">Missing INCI ({statusCounts.total - statusCounts.hasInci})</option>
          <option value="has_desc">Has description ({statusCounts.hasDesc})</option>
          <option value="no_desc">Missing description ({statusCounts.total - statusCounts.hasDesc})</option>
          <option value="has_price">Has price ({statusCounts.hasPrice})</option>
          <option value="no_price">Missing price ({statusCounts.total - statusCounts.hasPrice})</option>
        </select>

        <select
          value={sealFilter}
          onChange={(e) => setSealFilter(e.target.value)}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All seals</option>
          {SEAL_FILTER_OPTIONS.map(({ key, label }) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        <select
          value={confidenceFilter}
          onChange={(e) => setConfidenceFilter(e.target.value as typeof confidenceFilter)}
          className="px-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm text-ink-light focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all appearance-none cursor-pointer"
        >
          <option value="">All confidence</option>
          <option value="high">High (80%+)</option>
          <option value="medium">Medium (50-79%)</option>
          <option value="low">Low (&lt;50%)</option>
        </select>

        <button
          onClick={() => { setVerifiedOnly(!verifiedOnly); setPage(1); }}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all ${
            verifiedOnly
              ? 'bg-sage-bg border-sage/20 text-sage'
              : 'bg-white border-ink/8 text-ink-muted hover:text-ink hover:border-ink/15'
          }`}
        >
          <span
            className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-all ${
              verifiedOnly ? 'bg-sage border-sage' : 'border-ink/20'
            }`}
          >
            {verifiedOnly && (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </span>
          Verified INCI only
        </button>

        <button
          onClick={() => { setExcludeKits(!excludeKits); setPage(1); }}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium border transition-all ${
            excludeKits
              ? 'bg-champagne/8 border-champagne/20 text-champagne-dark'
              : 'bg-white border-ink/8 text-ink-muted hover:text-ink hover:border-ink/15'
          }`}
        >
          <span
            className={`w-3.5 h-3.5 rounded-sm border flex items-center justify-center transition-all ${
              excludeKits ? 'bg-champagne border-champagne' : 'border-ink/20'
            }`}
          >
            {excludeKits && (
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                <path d="M2 5l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </span>
          Exclude kits
        </button>
      </motion.div>

      {/* Product List / Grid */}
      {filtered.length === 0 ? (
        <EmptyState title="No products found" description="Try adjusting your search or filters." />
      ) : viewMode === 'grid' ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
        >
          {filtered.map((product, i) => (
            <ProductCard key={product.id} product={product} index={i} onClick={() => setSelectedProductId(product.id)} />
          ))}
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <ProductListView products={filtered} onSelect={(id) => setSelectedProductId(id)} />
        </motion.div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.3 }}
          className="flex items-center justify-between pt-2"
        >
          <p className="text-sm text-ink-muted">
            Showing {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, totalProducts)} of {totalProducts} products
          </p>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage(1)}
              disabled={page === 1}
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-muted hover:text-ink hover:bg-ink/5 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              First
            </button>
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-muted hover:text-ink hover:bg-ink/5 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            <span className="px-3 py-1.5 text-xs font-medium tabular-nums text-ink">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-muted hover:text-ink hover:bg-ink/5 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next
            </button>
            <button
              onClick={() => setPage(totalPages)}
              disabled={page === totalPages}
              className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-ink-muted hover:text-ink hover:bg-ink/5 transition-all disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Last
            </button>
          </div>
        </motion.div>
      )}

      {/* Product Detail Modal */}
      <AnimatePresence>
        {selectedProductId && <ProductModal productId={selectedProductId} onClose={() => setSelectedProductId(null)} onSaved={refetch} />}
      </AnimatePresence>
    </div>
  );
}

// ── Product Card ──

const MAX_CARD_SEALS = 3;

function ProductCard({ product, index, onClick }: { product: Product; index: number; onClick: () => void }) {
  const [imgError, setImgError] = useState(false);
  const detected = product.product_labels?.detected ?? [];
  const inferred = product.product_labels?.inferred ?? [];
  const allSeals = [...detected, ...inferred];
  const visibleSeals = allSeals.slice(0, MAX_CARD_SEALS);
  const hiddenCount = allSeals.length - visibleSeals.length;
  const confidencePct = Math.round(product.confidence * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.3) }}
      onClick={onClick}
      className="bg-white rounded-2xl border border-ink/5 overflow-hidden shadow-sm cursor-pointer hover:shadow-md hover:border-champagne/20 transition-all group flex flex-col"
    >
      {/* Image */}
      <div className="relative aspect-square bg-cream-dark overflow-hidden">
        {product.image_url_main && !imgError ? (
          <img
            src={product.image_url_main}
            alt={cleanProductName(product.product_name)}
            className="w-full h-full object-contain group-hover:scale-105 transition-transform duration-500"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-ink-faint">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
            <span className="text-[10px] uppercase tracking-wider">No image</span>
          </div>
        )}

        {/* Confidence pill overlay */}
        <div className="absolute top-2.5 right-2.5">
          <span
            className={`inline-flex items-center gap-1 text-[10px] font-semibold tabular-nums px-2 py-0.5 rounded-full backdrop-blur-sm ${
              confidencePct >= 80
                ? 'bg-sage/90 text-white'
                : confidencePct >= 50
                  ? 'bg-amber/90 text-white'
                  : 'bg-ink/60 text-white'
            }`}
          >
            {confidencePct}%
          </span>
        </div>

        {/* Status badge overlay */}
        <div className="absolute top-2.5 left-2.5">
          <StatusBadge status={product.verification_status} />
        </div>
      </div>

      {/* Info */}
      <div className="p-4 flex-1 flex flex-col">
        <p className="text-[11px] font-medium uppercase tracking-wider text-champagne-dark">
          {formatBrandName(product.brand_slug)}
        </p>
        <h3 className="text-sm font-medium text-ink mt-0.5 line-clamp-2 leading-snug">
          {cleanProductName(product.product_name)}
        </h3>

        {product.product_type_normalized && (
          <span className="inline-block mt-1.5 text-[10px] text-ink-faint bg-ink/3 px-2 py-0.5 rounded-full w-fit">
            {product.product_type_normalized}
          </span>
        )}

        {/* Seals */}
        {allSeals.length > 0 && (
          <div className="mt-auto pt-3 flex flex-wrap items-center gap-1.5">
            {visibleSeals.map((seal) => {
              const isDetected = detected.includes(seal);
              const display = SEAL_DISPLAY[seal];
              return (
                <span
                  key={seal}
                  className={`inline-flex items-center gap-1 text-[10px] font-medium px-2 py-0.5 rounded-full ${
                    isDetected
                      ? 'bg-sage-bg text-sage border border-sage/10'
                      : 'bg-ink/3 text-ink-muted'
                  }`}
                >
                  {display?.label ?? seal}
                </span>
              );
            })}
            {hiddenCount > 0 && (
              <span className="text-[10px] text-ink-faint font-medium">+{hiddenCount}</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

// ── Field Presence Indicator ──

const FIELD_INDICATORS = [
  { key: 'inci', label: 'INCI', tip: 'INCI Ingredients' },
  { key: 'desc', label: 'Desc', tip: 'Description' },
  { key: 'usage', label: 'Use', tip: 'Usage Instructions' },
  { key: 'benefits', label: 'Ben', tip: 'Benefits & Claims' },
  { key: 'price', label: 'R$', tip: 'Price' },
  { key: 'img', label: 'Img', tip: 'Image' },
] as const;

type FieldKey = (typeof FIELD_INDICATORS)[number]['key'];

function getProductFields(p: Product): Record<FieldKey, 'ok' | 'error' | 'empty'> {
  const hasInci = (p.inci_ingredients?.length ?? 0) > 0;
  const inciError = (p.quality?.issues ?? []).some(
    (i) => i.field === 'inci_ingredients' && i.severity === 'error'
  );
  return {
    inci: inciError ? 'error' : hasInci ? 'ok' : 'empty',
    desc: p.description?.trim() ? 'ok' : 'empty',
    usage: p.usage_instructions?.trim() ? 'ok' : 'empty',
    benefits: (p.benefits_claims?.length ?? 0) > 0 ? 'ok' : 'empty',
    price: p.price ? 'ok' : 'empty',
    img: p.image_url_main ? 'ok' : 'empty',
  };
}

function FieldDot({ status, label }: { status: 'ok' | 'error' | 'empty'; label: string }) {
  return (
    <span
      className={`inline-flex items-center justify-center w-[26px] text-[9px] font-semibold tracking-wide rounded py-0.5 ${
        status === 'ok'
          ? 'bg-sage/10 text-sage'
          : status === 'error'
            ? 'bg-coral/10 text-coral'
            : 'bg-ink/4 text-ink-faint/60'
      }`}
      title={label}
    >
      {label}
    </span>
  );
}

// ── Shopify-Style List View ──

function ProductListView({ products, onSelect }: { products: Product[]; onSelect: (id: string) => void }) {
  return (
    <div className="bg-white rounded-2xl border border-ink/5 overflow-hidden shadow-sm">
      {/* Table Header */}
      <div className="grid grid-cols-[48px_1fr_110px_130px_180px_64px] items-center gap-3 px-4 py-2.5 bg-cream/50 border-b border-ink/5 text-[10px] uppercase tracking-wider text-ink-faint font-semibold">
        <span />
        <span>Product</span>
        <span>Status</span>
        <span>Type</span>
        <span className="text-center">Fields</span>
        <span className="text-right">Quality</span>
      </div>

      {/* Rows */}
      <div className="divide-y divide-ink/3">
        {products.map((product, i) => (
          <ProductListRow key={product.id} product={product} index={i} onClick={() => onSelect(product.id)} />
        ))}
      </div>
    </div>
  );
}

function ProductListRow({ product, index, onClick }: { product: Product; index: number; onClick: () => void }) {
  const [imgError, setImgError] = useState(false);
  const q = product.quality;
  const hasErrors = (q?.error_count ?? 0) > 0;
  const hasWarnings = (q?.warning_count ?? 0) > 0;
  const fields = getProductFields(product);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2, delay: Math.min(index * 0.015, 0.3) }}
      onClick={onClick}
      className={`grid grid-cols-[48px_1fr_110px_130px_180px_64px] items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-champagne/3 transition-colors group ${
        hasErrors ? 'bg-coral/[0.02]' : ''
      }`}
    >
      {/* Thumbnail */}
      <div className="w-12 h-12 rounded-lg bg-cream-dark overflow-hidden flex-shrink-0">
        {product.image_url_main && !imgError ? (
          <img
            src={product.image_url_main}
            alt={cleanProductName(product.product_name)}
            className="w-full h-full object-contain"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-ink-faint">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
          </div>
        )}
      </div>

      {/* Product Name + Brand */}
      <div className="min-w-0">
        <p className="text-sm font-medium text-ink truncate group-hover:text-champagne-dark transition-colors">
          {cleanProductName(product.product_name)}
        </p>
        <span className="text-[10px] font-medium uppercase tracking-wider text-champagne-dark">
          {formatBrandName(product.brand_slug)}
        </span>
      </div>

      {/* Status */}
      <div>
        <StatusBadge status={product.verification_status} />
      </div>

      {/* Type */}
      <div>
        {product.product_type_normalized ? (
          <span className="text-xs text-ink-light truncate block capitalize">{product.product_type_normalized.replace('_', ' ')}</span>
        ) : (
          <span className="text-xs text-ink-faint">—</span>
        )}
      </div>

      {/* Field Indicators */}
      <div className="flex items-center gap-1">
        {FIELD_INDICATORS.map(({ key, label }) => (
          <FieldDot key={key} status={fields[key]} label={label} />
        ))}
      </div>

      {/* Quality */}
      <div className="text-right">
        {q ? (
          <div className="inline-flex items-center gap-1.5">
            {hasErrors ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-coral bg-coral/8 px-2 py-0.5 rounded-md tabular-nums">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                </svg>
                {q.error_count}
              </span>
            ) : hasWarnings ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber bg-amber/8 px-2 py-0.5 rounded-md tabular-nums">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M12 9v4" /><path d="M12 17h.01" />
                </svg>
                {q.warning_count}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-sage bg-sage/8 px-2 py-0.5 rounded-md">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <path d="M20 6L9 17l-5-5" />
                </svg>
              </span>
            )}
          </div>
        ) : (
          <span className="text-xs text-ink-faint">—</span>
        )}
      </div>
    </motion.div>
  );
}

// ── Field Validation ──

type FieldStatus = 'ok' | 'warn' | 'missing';

function getFieldStatus(field: string, value: unknown): FieldStatus {
  const isEmpty =
    !value || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && value.length === 0);
  if (field === 'inci_ingredients' && Array.isArray(value) && value.length > 0) {
    if ((value as string[]).some((v) => v.length > 80 || /\.\s/.test(v))) return 'warn';
    return 'ok';
  }
  return isEmpty ? 'missing' : 'ok';
}

function StatusDot({ status }: { status: FieldStatus }) {
  return (
    <span
      className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
        status === 'ok' ? 'bg-sage' : status === 'warn' ? 'bg-amber' : 'bg-ink/15'
      }`}
    />
  );
}

function FieldLabel({ label, status, required }: { label: string; status: FieldStatus; required?: boolean }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-1.5">
      <StatusDot status={status} />
      {label}
      {required && <span className="text-coral/50">*</span>}
      {status === 'warn' && (
        <span className="text-amber text-[10px] normal-case tracking-normal font-normal ml-1">Needs review</span>
      )}
    </label>
  );
}

// ── Tag Editor ──

function TagEditor({
  tags,
  onChange,
  placeholder,
}: {
  tags: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState('');

  const addTags = (text: string) => {
    const newTags = text
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t && !tags.includes(t));
    if (newTags.length > 0) onChange([...tags, ...newTags]);
    setInput('');
  };

  const removeTag = (index: number) => onChange(tags.filter((_, i) => i !== index));

  return (
    <div className="bg-cream rounded-xl p-3 space-y-2">
      {tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 text-xs bg-white px-2.5 py-1 rounded-lg border border-ink/8"
            >
              <span className="max-w-[240px] truncate">{tag}</span>
              <button
                type="button"
                onClick={() => removeTag(i)}
                className="text-ink-faint hover:text-coral transition-colors font-medium"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addTags(input);
            }
          }}
          placeholder={placeholder ?? 'Type and press Enter (comma-separated for multiple)'}
          className="flex-1 text-xs px-3 py-1.5 bg-white border border-ink/8 rounded-lg focus:outline-none focus:ring-1 focus:ring-champagne/30"
        />
        <button
          type="button"
          onClick={() => addTags(input)}
          className="text-xs px-3 py-1.5 bg-champagne/10 text-champagne-dark rounded-lg hover:bg-champagne/20 transition-colors font-medium"
        >
          Add
        </button>
      </div>
      {tags.length === 0 && <p className="text-[10px] text-ink-faint">Separate multiple items with commas</p>}
    </div>
  );
}

// ── Quality Issues Banner ──

function QualityIssuesBanner({ issues }: { issues: Array<{ field: string; code: string; severity: string; message: string; details: string }> }) {
  const errors = issues.filter((i) => i.severity === 'error');
  const warnings = issues.filter((i) => i.severity === 'warning');
  const infos = issues.filter((i) => i.severity === 'info');

  return (
    <div className="space-y-2">
      {errors.length > 0 && (
        <div className="bg-coral/5 border border-coral/15 rounded-xl p-3 space-y-1.5">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-coral flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
            </svg>
            {errors.length} Error{errors.length > 1 ? 's' : ''} — Must Fix
          </p>
          {errors.map((issue, i) => (
            <div key={i} className="text-xs text-coral/90">
              <span className="font-medium">{issue.field}:</span> {issue.message}
              {issue.details && <span className="block text-[10px] text-coral/60 mt-0.5 truncate">{issue.details}</span>}
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="bg-amber/5 border border-amber/15 rounded-xl p-3 space-y-1.5">
          <p className="text-[11px] uppercase tracking-wider font-semibold text-amber flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
              <path d="M12 9v4" /><path d="M12 17h.01" />
            </svg>
            {warnings.length} Warning{warnings.length > 1 ? 's' : ''} — Review
          </p>
          {warnings.map((issue, i) => (
            <div key={i} className="text-xs text-amber/90">
              <span className="font-medium">{issue.field}:</span> {issue.message}
              {issue.details && <span className="block text-[10px] text-amber/60 mt-0.5 truncate">{issue.details}</span>}
            </div>
          ))}
        </div>
      )}
      {infos.length > 0 && (
        <div className="bg-ink/3 border border-ink/5 rounded-xl p-3 space-y-1">
          {infos.map((issue, i) => (
            <div key={i} className="text-xs text-ink-muted">
              <span className="font-medium">{issue.field}:</span> {issue.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Product Detail Modal (Editable) ──

function ProductModal({
  productId,
  onClose,
  onSaved,
}: {
  productId: string;
  onClose: () => void;
  onSaved?: () => void;
}) {
  const [product, setProduct] = useState<Product | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [imgError, setImgError] = useState(false);
  const [showEvidence, setShowEvidence] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ text: string; ok: boolean } | null>(null);

  // Form fields
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [usageInstr, setUsageInstr] = useState('');
  const [inci, setInci] = useState<string[]>([]);
  const [benefits, setBenefits] = useState<string[]>([]);
  const [price, setPrice] = useState('');
  const [currency, setCurrency] = useState('');
  const [sizeVol, setSizeVol] = useState('');
  const [gender, setGender] = useState('');
  const [prodType, setProdType] = useState('');
  const [lineCol, setLineCol] = useState('');
  const [imageUrl, setImageUrl] = useState('');
  const [verStatus, setVerStatus] = useState('');

  // Load product
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setImgError(false);
    getProduct(productId)
      .then((p) => {
        if (!cancelled) {
          setProduct(p);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to load');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [productId]);

  // Populate form when product loads
  useEffect(() => {
    if (!product) return;
    setName(sanitizeText(product.product_name) || '');
    setDescription(sanitizeText(product.description ?? '') || '');
    setUsageInstr(sanitizeText(product.usage_instructions ?? '') || '');
    setInci(product.inci_ingredients ?? []);
    setBenefits((product.benefits_claims ?? []).map(sanitizeText));
    setPrice(product.price != null ? String(product.price) : '');
    setCurrency(product.currency ?? '');
    setSizeVol(product.size_volume ?? '');
    setGender(product.gender_target ?? '');
    setProdType(product.product_type_normalized ?? '');
    setLineCol(product.line_collection ?? '');
    setImageUrl(product.image_url_main ?? '');
    setVerStatus(product.verification_status ?? '');
  }, [product]);

  // Field validations
  const v = useMemo(
    () => ({
      product_name: getFieldStatus('product_name', name),
      inci_ingredients: getFieldStatus('inci_ingredients', inci),
      description: getFieldStatus('description', description),
      product_type_normalized: getFieldStatus('product_type_normalized', prodType),
      image_url_main: getFieldStatus('image_url_main', imageUrl),
      price: getFieldStatus('price', price),
      size_volume: getFieldStatus('size_volume', sizeVol),
      gender_target: getFieldStatus('gender_target', gender),
      line_collection: getFieldStatus('line_collection', lineCol),
      usage_instructions: getFieldStatus('usage_instructions', usageInstr),
      benefits_claims: getFieldStatus('benefits_claims', benefits),
    }),
    [name, inci, description, prodType, imageUrl, price, sizeVol, gender, lineCol, usageInstr, benefits]
  );

  const counts = useMemo(() => {
    const vals = Object.values(v);
    return {
      ok: vals.filter((s) => s === 'ok').length,
      warn: vals.filter((s) => s === 'warn').length,
      missing: vals.filter((s) => s === 'missing').length,
      total: vals.length,
    };
  }, [v]);

  // Save handler
  const handleSave = async () => {
    if (!product) return;
    setSaving(true);
    setSaveMsg(null);
    try {
      const data: Record<string, unknown> = {};
      if (name !== sanitizeText(product.product_name)) data.product_name = name;
      if (description !== sanitizeText(product.description ?? '')) data.description = description;
      if (usageInstr !== sanitizeText(product.usage_instructions ?? '')) data.usage_instructions = usageInstr;
      if (JSON.stringify(inci) !== JSON.stringify(product.inci_ingredients ?? [])) data.inci_ingredients = inci;
      if (JSON.stringify(benefits) !== JSON.stringify((product.benefits_claims ?? []).map(sanitizeText)))
        data.benefits_claims = benefits;
      const origPrice = product.price != null ? String(product.price) : '';
      if (price !== origPrice) data.price = price ? parseFloat(price) : null;
      if (currency !== (product.currency ?? '')) data.currency = currency || null;
      if (sizeVol !== (product.size_volume ?? '')) data.size_volume = sizeVol || null;
      if (gender !== (product.gender_target ?? '')) data.gender_target = gender || null;
      if (prodType !== (product.product_type_normalized ?? '')) data.product_type_normalized = prodType || null;
      if (lineCol !== (product.line_collection ?? '')) data.line_collection = lineCol || null;
      if (imageUrl !== (product.image_url_main ?? '')) data.image_url_main = imageUrl || null;
      if (verStatus !== (product.verification_status ?? '')) data.verification_status = verStatus;
      if (product.product_labels?.manually_overridden) {
        data.product_labels = product.product_labels;
      }

      if (Object.keys(data).length === 0) {
        setSaveMsg({ text: 'No changes to save', ok: true });
        setSaving(false);
        return;
      }

      const updated = await updateProduct(product.id, data as Partial<Product>);
      setProduct({ ...product, ...updated });
      setSaveMsg({ text: 'Saved!', ok: true });
      onSaved?.();
    } catch (e) {
      setSaveMsg({ text: e instanceof Error ? e.message : 'Save failed', ok: false });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  };

  // Evidence groups
  const evidenceGroups = useMemo(() => {
    if (!product?.evidence) return { product: [], labels: [] };
    const pe: ProductEvidence[] = [];
    const le: ProductEvidence[] = [];
    for (const ev of product.evidence) {
      (ev.field_name.startsWith('label:') ? le : pe).push(ev);
    }
    return { product: pe, labels: le };
  }, [product?.evidence]);

  const inputCls =
    'w-full text-sm px-3 py-2 bg-white border border-ink/8 rounded-lg focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all';
  const textareaCls = `${inputCls} resize-none`;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-ink/30 backdrop-blur-sm z-50 flex items-start justify-center p-4 pt-[5vh] overflow-y-auto"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 20 }}
        transition={{ duration: 0.3 }}
        className="bg-white rounded-2xl shadow-xl max-w-3xl w-full my-4 flex flex-col max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {loading && (
          <div className="p-12 flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-8 h-8 border-2 border-champagne/30 border-t-champagne rounded-full animate-spin" />
              <span className="text-sm text-ink-muted">Loading product...</span>
            </div>
          </div>
        )}

        {error && (
          <div className="p-12 text-center">
            <p className="text-sm text-coral">{error}</p>
            <button onClick={onClose} className="mt-3 text-sm text-ink-muted hover:text-ink transition-colors">
              Close
            </button>
          </div>
        )}

        {product && (
          <>
            {/* Header */}
            <div className="relative p-6 pb-4 border-b border-ink/5 flex-shrink-0">
              <button
                onClick={onClose}
                className="absolute top-4 right-4 p-2 rounded-lg hover:bg-ink/5 transition-colors text-ink-muted z-10"
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 6L6 18M6 6l12 12" />
                </svg>
              </button>

              <div className="flex gap-5">
                <div className="w-24 h-24 rounded-xl bg-cream-dark overflow-hidden flex-shrink-0">
                  {imageUrl && !imgError ? (
                    <img
                      src={imageUrl}
                      alt={name}
                      className="w-full h-full object-contain"
                      onError={() => setImgError(true)}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-ink-faint">
                      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <circle cx="8.5" cy="8.5" r="1.5" />
                        <path d="M21 15l-5-5L5 21" />
                      </svg>
                    </div>
                  )}
                </div>

                <div className="flex-1 min-w-0 pr-8">
                  <p className="text-xs font-medium uppercase tracking-wider text-champagne-dark">
                    {formatBrandName(product.brand_slug)}
                  </p>
                  <h2 className="font-display text-xl font-semibold text-ink mt-0.5 leading-snug">
                    {name || 'Untitled Product'}
                  </h2>
                  <div className="flex items-center gap-2 mt-2 flex-wrap">
                    <StatusBadge status={verStatus} size="md" />
                    <span
                      className={`text-xs font-medium tabular-nums px-2 py-0.5 rounded-full ${
                        product.confidence >= 0.8
                          ? 'bg-sage-bg text-sage'
                          : product.confidence >= 0.5
                            ? 'bg-amber-bg text-amber'
                            : 'bg-ink/5 text-ink-muted'
                      }`}
                    >
                      {Math.round(product.confidence * 100)}% confidence
                    </span>
                  </div>
                </div>
              </div>

              {/* Validation summary */}
              <div className="mt-4 flex items-center gap-4 text-xs">
                <span className="flex items-center gap-1.5 text-sage font-medium">
                  <span className="w-2 h-2 rounded-full bg-sage" /> {counts.ok}/{counts.total} complete
                </span>
                {counts.warn > 0 && (
                  <span className="flex items-center gap-1.5 text-amber font-medium">
                    <span className="w-2 h-2 rounded-full bg-amber" /> {counts.warn} warning
                    {counts.warn > 1 ? 's' : ''}
                  </span>
                )}
                {counts.missing > 0 && (
                  <span className="flex items-center gap-1.5 text-ink-faint font-medium">
                    <span className="w-2 h-2 rounded-full bg-ink/15" /> {counts.missing} missing
                  </span>
                )}
              </div>
            </div>

            {/* Scrollable Body */}
            <div className="p-6 space-y-5 overflow-y-auto flex-1">
              {/* Quality Issues Banner */}
              {product.quality && product.quality.issues.length > 0 && (
                <QualityIssuesBanner issues={product.quality.issues} />
              )}
              {/* Basic Info */}
              <div className="space-y-4">
                <div>
                  <FieldLabel label="Product Name" status={v.product_name} required />
                  <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <FieldLabel label="Product Type" status={v.product_type_normalized} />
                    <input
                      value={prodType}
                      onChange={(e) => setProdType(e.target.value)}
                      placeholder="e.g. Shampoo, Mascara..."
                      className={inputCls}
                    />
                  </div>
                  <div>
                    <FieldLabel label="Gender Target" status={v.gender_target} />
                    <select value={gender} onChange={(e) => setGender(e.target.value)} className={inputCls}>
                      <option value="">Not set</option>
                      <option value="female">Female</option>
                      <option value="male">Male</option>
                      <option value="unisex">Unisex</option>
                      <option value="unknown">Unknown</option>
                    </select>
                  </div>
                </div>

                <div>
                  <FieldLabel label="Line / Collection" status={v.line_collection} />
                  <input
                    value={lineCol}
                    onChange={(e) => setLineCol(e.target.value)}
                    placeholder="e.g. Gold Black, Millenar..."
                    className={inputCls}
                  />
                </div>
              </div>

              {/* Pricing */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <FieldLabel label="Price" status={v.price} />
                  <input
                    type="number"
                    step="0.01"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="0.00"
                    className={inputCls}
                  />
                </div>
                <div>
                  <FieldLabel label="Currency" status={getFieldStatus('currency', currency)} />
                  <input
                    value={currency}
                    onChange={(e) => setCurrency(e.target.value)}
                    placeholder="BRL"
                    className={inputCls}
                  />
                </div>
                <div>
                  <FieldLabel label="Size / Volume" status={v.size_volume} />
                  <input
                    value={sizeVol}
                    onChange={(e) => setSizeVol(e.target.value)}
                    placeholder="e.g. 300ml"
                    className={inputCls}
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <FieldLabel label="Description" status={v.description} />
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Product description..."
                  className={textareaCls}
                />
              </div>

              {/* Usage Instructions */}
              <div>
                <FieldLabel label="Usage Instructions" status={v.usage_instructions} />
                <textarea
                  value={usageInstr}
                  onChange={(e) => setUsageInstr(e.target.value)}
                  rows={2}
                  placeholder="How to use this product..."
                  className={textareaCls}
                />
              </div>

              {/* Benefits & Claims */}
              <div>
                <FieldLabel label={`Benefits & Claims (${benefits.length})`} status={v.benefits_claims} />
                <TagEditor tags={benefits} onChange={setBenefits} placeholder="Add benefit or claim..." />
              </div>

              {/* INCI Ingredients — highlighted section */}
              <div className="border-2 border-dashed border-ink/8 rounded-xl p-4 space-y-2">
                <FieldLabel label={`INCI Ingredients (${inci.length})`} status={v.inci_ingredients} required />
                {v.inci_ingredients === 'warn' && (
                  <p className="text-xs text-amber bg-amber-bg px-3 py-1.5 rounded-lg">
                    Some entries look like marketing text instead of real INCI ingredient names. Please review and
                    correct.
                  </p>
                )}
                <TagEditor
                  tags={inci}
                  onChange={setInci}
                  placeholder="Add ingredient (comma-separated for multiple)..."
                />
              </div>

              {/* Image URL */}
              <div>
                <FieldLabel label="Image URL" status={v.image_url_main} />
                <input
                  value={imageUrl}
                  onChange={(e) => {
                    setImageUrl(e.target.value);
                    setImgError(false);
                  }}
                  placeholder="https://..."
                  className={inputCls}
                />
              </div>

              {/* Verification Status */}
              <div>
                <FieldLabel label="Verification Status" status={getFieldStatus('verification_status', verStatus)} />
                <select value={verStatus} onChange={(e) => setVerStatus(e.target.value)} className={inputCls}>
                  <option value="verified_inci">Verified INCI</option>
                  <option value="catalog_only">Catalog Only</option>
                  <option value="quarantined">Quarantined</option>
                </select>
              </div>

              {/* Quality Seals (editable) */}
              <SealEditor
                labels={product.product_labels}
                onChange={(updated) => {
                  setProduct({ ...product, product_labels: updated });
                }}
              />

              {/* Source URL */}
              {product.product_url && (
                <Section title="Source URL">
                  <a
                    href={product.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-champagne-dark hover:underline break-all"
                  >
                    {product.product_url}
                  </a>
                </Section>
              )}

              {/* Evidence Trail */}
              {product.evidence && product.evidence.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowEvidence(!showEvidence)}
                    className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-ink-muted font-semibold hover:text-ink transition-colors"
                  >
                    <svg
                      width="12"
                      height="12"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      className={`transition-transform ${showEvidence ? 'rotate-90' : ''}`}
                    >
                      <path d="M9 18l6-6-6-6" />
                    </svg>
                    Evidence Trail ({product.evidence.length} records)
                  </button>

                  <AnimatePresence>
                    {showEvidence && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-3 space-y-4">
                          {evidenceGroups.product.length > 0 && (
                            <div>
                              <p className="text-[10px] uppercase tracking-wider text-ink-faint font-medium mb-2">
                                Extraction Evidence
                              </p>
                              <div className="space-y-1.5">
                                {evidenceGroups.product.map((ev) => (
                                  <EvidenceRow key={ev.id} ev={ev} />
                                ))}
                              </div>
                            </div>
                          )}

                          {evidenceGroups.labels.length > 0 && (
                            <div>
                              <p className="text-[10px] uppercase tracking-wider text-ink-faint font-medium mb-2">
                                Label Detection Evidence
                              </p>
                              <div className="space-y-1.5">
                                {evidenceGroups.labels.map((ev) => (
                                  <EvidenceRow key={ev.id} ev={ev} />
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-ink/5 flex items-center justify-between flex-shrink-0">
              <div className="text-xs text-ink-faint">
                {product.updated_at && `Last updated: ${new Date(product.updated_at).toLocaleDateString()}`}
              </div>
              <div className="flex items-center gap-3">
                {saveMsg && (
                  <span className={`text-xs font-medium ${saveMsg.ok ? 'text-sage' : 'text-coral'}`}>
                    {saveMsg.text}
                  </span>
                )}
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-5 py-2 bg-champagne text-white text-sm font-medium rounded-xl hover:bg-champagne-dark transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </div>
          </>
        )}
      </motion.div>
    </motion.div>
  );
}

// ── Seal Editor ──

function SealEditor({ labels, onChange }: { labels: Product['product_labels']; onChange: (updated: Product['product_labels']) => void }) {
  const detected = labels?.detected ?? [];
  const inferred = labels?.inferred ?? [];
  const allActive = [...detected, ...inferred];
  const allSealKeys = Object.keys(SEAL_DISPLAY);
  const inactive = allSealKeys.filter((k) => !allActive.includes(k));

  function toggleSeal(seal: string) {
    const current = labels ?? { detected: [], inferred: [], confidence: 0, sources: [], manually_verified: false, manually_overridden: false };
    const isActive = [...(current.detected ?? []), ...(current.inferred ?? [])].includes(seal);

    let newDetected = [...(current.detected ?? [])];
    let newInferred = [...(current.inferred ?? [])];

    if (isActive) {
      newDetected = newDetected.filter((s) => s !== seal);
      newInferred = newInferred.filter((s) => s !== seal);
    } else {
      newDetected = [...newDetected, seal];
    }

    onChange({
      ...current,
      detected: newDetected,
      inferred: newInferred,
      manually_overridden: true,
    });
  }

  return (
    <div className="space-y-3">
      <p className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold flex items-center gap-2">
        Quality Seals
        {labels?.manually_overridden && (
          <span className="text-[9px] normal-case tracking-normal px-1.5 py-0.5 bg-amber-bg text-amber rounded">manually edited</span>
        )}
      </p>

      {/* Active seals */}
      {allActive.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {detected.map((seal) => (
            <button
              key={seal}
              type="button"
              onClick={() => toggleSeal(seal)}
              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-sage-bg text-sage border border-sage/15 hover:bg-sage/20 transition-colors"
            >
              {SEAL_DISPLAY[seal]?.label ?? seal}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          ))}
          {inferred.map((seal) => (
            <button
              key={seal}
              type="button"
              onClick={() => toggleSeal(seal)}
              className="inline-flex items-center gap-1.5 text-[11px] font-medium px-2.5 py-1 rounded-lg bg-ink/3 text-ink-muted hover:bg-ink/8 transition-colors"
            >
              {SEAL_DISPLAY[seal]?.label ?? seal}
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M18 6L6 18M6 6l12 12" /></svg>
            </button>
          ))}
        </div>
      )}

      {/* Inactive seals — available to add */}
      {inactive.length > 0 && (
        <div>
          <p className="text-[10px] text-ink-faint mb-1.5">Click to add:</p>
          <div className="flex flex-wrap gap-1">
            {inactive.map((seal) => (
              <button
                key={seal}
                type="button"
                onClick={() => toggleSeal(seal)}
                className="text-[10px] px-2 py-0.5 rounded bg-ink/3 text-ink-faint hover:bg-champagne/10 hover:text-champagne-dark transition-colors"
              >
                + {SEAL_DISPLAY[seal]?.label ?? seal}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Confidence */}
      {labels && (
        <p className="text-[10px] text-ink-faint">
          Label confidence: <span className="font-medium tabular-nums">{Math.round(labels.confidence * 100)}%</span>
        </p>
      )}
    </div>
  );
}

// ── Helper Components ──

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}

function EvidenceRow({ ev }: { ev: ProductEvidence }) {
  const fieldLabel = ev.field_name.startsWith('label:')
    ? ev.field_name.replace('label:', '').replace(/_/g, ' ')
    : ev.field_name.replace(/_/g, ' ');
  const timestamp = ev.extracted_at ? new Date(ev.extracted_at).toLocaleDateString() : null;

  return (
    <div className="px-3 py-2.5 bg-cream/70 rounded-lg text-xs space-y-1">
      <div className="flex items-center gap-2">
        <span className="font-semibold text-ink capitalize">{fieldLabel}</span>
        {ev.extraction_method && (
          <span className="text-[10px] uppercase tracking-wider text-ink-faint px-1.5 py-0.5 bg-ink/5 rounded">
            {ev.extraction_method}
          </span>
        )}
        {timestamp && (
          <span className="text-[10px] text-ink-faint ml-auto tabular-nums">{timestamp}</span>
        )}
      </div>
      {ev.raw_source_text && (
        <p className="text-ink-muted leading-relaxed line-clamp-2">{ev.raw_source_text}</p>
      )}
      {ev.source_url && (
        <a
          href={ev.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[11px] text-champagne-dark hover:underline break-all"
        >
          {ev.source_url}
        </a>
      )}
      {ev.evidence_locator && (
        <p className="text-[10px] text-ink-faint font-mono">{ev.evidence_locator}</p>
      )}
    </div>
  );
}
