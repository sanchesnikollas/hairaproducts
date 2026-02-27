import { useState, useMemo, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { getProducts, getProduct, getFocusBrand, updateProduct } from '../lib/api';
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

export default function ProductBrowser() {
  const [search, setSearch] = useState('');
  const [brandFilter, setBrandFilter] = useState('');
  const [focusBrand, setFocusBrand] = useState<string | null>(null);
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [sealFilter, setSealFilter] = useState('');
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);

  useEffect(() => {
    getFocusBrand()
      .then(({ focus_brand }) => {
        if (focus_brand) setFocusBrand(focus_brand);
      })
      .catch(() => {});
  }, []);

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
        const labels = p.product_labels;
        if (!labels) return false;
        return (labels.detected ?? []).includes(sealFilter) || (labels.inferred ?? []).includes(sealFilter);
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
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">Product Browser</h1>
          {focusBrand && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-champagne/10 text-champagne-dark border border-champagne/15">
              <span className="w-1.5 h-1.5 rounded-full bg-champagne" />
              {formatBrandName(focusBrand)}
            </span>
          )}
        </div>
        <p className="mt-1.5 text-sm text-ink-muted">
          {filtered.length} product{filtered.length !== 1 ? 's' : ''} with verified INCI ingredient data
        </p>
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
          onChange={(e) => setBrandFilter(e.target.value)}
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

        <button
          onClick={() => setVerifiedOnly(!verifiedOnly)}
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
      </motion.div>

      {/* Product Grid */}
      {filtered.length === 0 ? (
        <EmptyState title="No products found" description="Try adjusting your search or filters." />
      ) : (
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
  const [showEvidence, setShowEvidence] = useState(false);
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

              {/* Quality Seals (read-only) */}
              <SealSection labels={product.product_labels} />

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

// ── Seal Section ──

function SealSection({ labels }: { labels: Product['product_labels'] }) {
  if (!labels) return null;
  const detected = labels.detected ?? [];
  const inferred = labels.inferred ?? [];
  if (detected.length === 0 && inferred.length === 0) return null;

  return (
    <div className="space-y-3">
      {/* Detected seals — high priority */}
      {detected.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-sage font-semibold mb-2 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <path d="M9 12l2 2 4-4" />
              <circle cx="12" cy="12" r="10" />
            </svg>
            Detected from product text
          </p>
          <div className="flex flex-wrap gap-2">
            {detected.map((seal) => (
              <span
                key={seal}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-sage-bg text-sage border border-sage/15"
              >
                {SEAL_DISPLAY[seal]?.label ?? seal}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Inferred seals — lower priority */}
      {inferred.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wider text-ink-faint font-semibold mb-2 flex items-center gap-1.5">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2l2.4 7.4h7.6l-6 4.6 2.3 7-6.3-4.6-6.3 4.6 2.3-7-6-4.6h7.6z" />
            </svg>
            Inferred from INCI analysis
          </p>
          <div className="flex flex-wrap gap-1.5">
            {inferred.map((seal) => (
              <span
                key={seal}
                className="inline-flex items-center text-[11px] font-medium px-2.5 py-1 rounded-lg bg-ink/3 text-ink-muted"
              >
                {SEAL_DISPLAY[seal]?.label ?? seal}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Confidence */}
      <p className="text-[10px] text-ink-faint">
        Label confidence: <span className="font-medium tabular-nums">{Math.round(labels.confidence * 100)}%</span>
      </p>
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

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-cream rounded-lg px-3 py-2.5">
      <span className="text-[10px] uppercase tracking-wider text-ink-faint block">{label}</span>
      <p className="text-sm text-ink-light mt-0.5 truncate">{value}</p>
    </div>
  );
}

function EvidenceRow({ ev }: { ev: ProductEvidence }) {
  const fieldLabel = ev.field_name.startsWith('label:') ? ev.field_name.replace('label:', '') : ev.field_name;

  return (
    <div className="flex items-start gap-3 px-3 py-2 bg-cream/70 rounded-lg text-xs">
      <span className="font-medium text-ink whitespace-nowrap min-w-[100px]">{fieldLabel}</span>
      <span className="text-ink-muted flex-1 break-all line-clamp-1">{ev.raw_source_text ?? '—'}</span>
      <span className="text-[10px] uppercase tracking-wider text-ink-faint whitespace-nowrap">
        {ev.extraction_method ?? ''}
      </span>
    </div>
  );
}
