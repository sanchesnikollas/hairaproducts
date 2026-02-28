import { useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { getBrandCoverage, getProducts } from '../lib/api';
import { useAPI } from '../hooks/useAPI';
import ProgressBar from '../components/ProgressBar';
import StatusBadge from '../components/StatusBadge';
import LoadingState, { ErrorState } from '../components/LoadingState';

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export default function BrandDetail() {
  const { slug } = useParams<{ slug: string }>();
  const { data: coverage, loading, error } = useAPI(
    () => getBrandCoverage(slug!),
    [slug]
  );
  const { data: productsResponse } = useAPI(
    () => getProducts({ brand: slug, per_page: 1000, exclude_kits: false }),
    [slug]
  );

  const products = productsResponse?.items ?? [];

  const CATEGORY_LABELS: Record<string, string> = {
    shampoo: 'Shampoo',
    condicionador: 'Condicionador',
    mascara: 'Mascara',
    tratamento: 'Tratamento',
    leave_in: 'Leave-in',
    oleo_serum: 'Oleo & Serum',
    styling: 'Styling',
    coloracao: 'Coloracao',
  };

  const categoryBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of products) {
      const t = p.product_category || 'Other';
      counts[t] = (counts[t] || 0) + 1;
    }
    return Object.entries(counts)
      .sort((a, b) => b[1] - a[1]);
  }, [products]);

  const sealBreakdown = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const p of products) {
      const labels = p.product_labels;
      if (!labels) continue;
      for (const s of [...(labels.detected ?? []), ...(labels.inferred ?? [])]) {
        counts[s] = (counts[s] || 0) + 1;
      }
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [products]);

  if (loading) return <LoadingState message="Loading brand details..." />;
  if (error) return <ErrorState message={error} />;
  if (!coverage) return null;

  const rateColor = coverage.verified_inci_rate >= 0.8 ? 'sage' : coverage.verified_inci_rate >= 0.5 ? 'champagne' : 'coral';

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
        <div className="flex items-center gap-3 mb-1">
          <Link
            to="/brands"
            className="text-sm text-ink-muted hover:text-ink transition-colors flex items-center gap-1"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            Brands
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
            {formatBrandName(slug!)}
          </h1>
          <StatusBadge status={coverage.status} size="md" />
        </div>
        {coverage.last_run && (
          <p className="mt-1 text-sm text-ink-muted">
            Last pipeline run: {new Date(coverage.last_run).toLocaleDateString()}
          </p>
        )}
      </motion.div>

      {/* Key Metrics */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        <MetricCard label="Discovered" value={coverage.discovered_total} />
        <MetricCard label="Extracted" value={coverage.extracted_total} />
        <MetricCard label="Verified INCI" value={coverage.verified_inci_total} accent />
        <MetricCard label="Quarantined" value={coverage.quarantined_total} warn={coverage.quarantined_total > 0} />
      </motion.div>

      {/* Verification Rate */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="bg-white rounded-xl border border-ink/5 p-6 shadow-sm"
      >
        <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
          INCI Verification Rate
        </h2>
        <ProgressBar value={coverage.verified_inci_rate} color={rateColor} />
        <div className="mt-3 grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-lg font-display font-semibold text-sage">{coverage.verified_inci_total}</p>
            <p className="text-[10px] uppercase tracking-wider text-ink-faint">Verified</p>
          </div>
          <div>
            <p className="text-lg font-display font-semibold text-amber">{coverage.catalog_only_total}</p>
            <p className="text-[10px] uppercase tracking-wider text-ink-faint">Catalog Only</p>
          </div>
          <div>
            <p className="text-lg font-display font-semibold text-coral">{coverage.quarantined_total}</p>
            <p className="text-[10px] uppercase tracking-wider text-ink-faint">Quarantined</p>
          </div>
        </div>
      </motion.div>

      {/* Discovery Breakdown */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.2 }}
        className="grid grid-cols-1 md:grid-cols-2 gap-6"
      >
        {/* Product Categories */}
        <div className="bg-white rounded-xl border border-ink/5 p-6 shadow-sm">
          <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
            Product Categories
          </h2>
          {categoryBreakdown.length === 0 ? (
            <p className="text-sm text-ink-faint">No products loaded yet.</p>
          ) : (
            <div className="space-y-2">
              {categoryBreakdown.map(([cat, count]) => (
                <div key={cat} className="flex items-center justify-between">
                  <span className="text-sm text-ink-light">{CATEGORY_LABELS[cat] || cat}</span>
                  <span className="text-sm font-medium tabular-nums text-ink">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quality Seals */}
        <div className="bg-white rounded-xl border border-ink/5 p-6 shadow-sm">
          <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
            Quality Seals
          </h2>
          {sealBreakdown.length === 0 ? (
            <p className="text-sm text-ink-faint">No seals detected yet.</p>
          ) : (
            <div className="space-y-2">
              {sealBreakdown.map(([seal, count]) => (
                <div key={seal} className="flex items-center justify-between">
                  <span className="text-sm text-ink-light">
                    {seal.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </span>
                  <span className="text-sm font-medium tabular-nums text-ink">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>

      {/* Discovery Funnel */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.25 }}
        className="bg-white rounded-xl border border-ink/5 p-6 shadow-sm"
      >
        <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
          Discovery Funnel
        </h2>
        <div className="space-y-3">
          <FunnelRow label="URLs Discovered" value={coverage.discovered_total} total={coverage.discovered_total} />
          <FunnelRow label="Hair Products" value={coverage.hair_total} total={coverage.discovered_total} />
          <FunnelRow label="Extracted" value={coverage.extracted_total} total={coverage.discovered_total} />
          <FunnelRow label="Verified INCI" value={coverage.verified_inci_total} total={coverage.discovered_total} />
        </div>
        {(coverage.kits_total > 0 || coverage.non_hair_total > 0) && (
          <div className="mt-4 pt-3 border-t border-ink/5 flex gap-6 text-xs text-ink-muted">
            {coverage.kits_total > 0 && <span>{coverage.kits_total} kits excluded</span>}
            {coverage.non_hair_total > 0 && <span>{coverage.non_hair_total} non-hair products</span>}
          </div>
        )}
      </motion.div>

      {/* Actions */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.3 }}
        className="flex gap-3"
      >
        <Link
          to={`/products?brand=${slug}`}
          className="px-5 py-2.5 bg-champagne text-white text-sm font-medium rounded-xl hover:bg-champagne-dark transition-colors"
        >
          Browse {coverage.extracted_total} Products
        </Link>
        {coverage.quarantined_total > 0 && (
          <Link
            to="/quarantine"
            className="px-5 py-2.5 bg-coral/10 text-coral text-sm font-medium rounded-xl hover:bg-coral/20 transition-colors"
          >
            Review {coverage.quarantined_total} Quarantined
          </Link>
        )}
      </motion.div>
    </div>
  );
}

// ── Sub-components ──

function MetricCard({ label, value, accent, warn }: { label: string; value: number; accent?: boolean; warn?: boolean }) {
  const color = warn ? 'text-coral' : accent ? 'text-champagne-dark' : 'text-ink';
  return (
    <div className="bg-white rounded-xl border border-ink/5 p-5 shadow-sm">
      <p className="text-xs uppercase tracking-wider text-ink-muted mb-1">{label}</p>
      <p className={`text-2xl font-display font-semibold ${color}`}>{value.toLocaleString()}</p>
    </div>
  );
}

function FunnelRow({ label, value, total }: { label: string; value: number; total: number }) {
  const pct = total > 0 ? value / total : 0;
  return (
    <div className="flex items-center gap-4">
      <span className="text-sm text-ink-light w-36 flex-shrink-0">{label}</span>
      <div className="flex-1 h-2 bg-ink/5 rounded-full overflow-hidden">
        <div
          className="h-full bg-champagne rounded-full transition-all"
          style={{ width: `${Math.round(pct * 100)}%` }}
        />
      </div>
      <span className="text-sm font-medium tabular-nums text-ink w-16 text-right">{value.toLocaleString()}</span>
    </div>
  );
}
