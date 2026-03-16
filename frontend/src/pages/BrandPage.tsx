import { useState, useMemo, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import ProductCard from '@/components/ProductCard';
import SealBadge from '@/components/SealBadge';
import LoadingState, { ErrorState, EmptyState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getBrandCoverage, getBrandProducts } from '@/lib/api';
import type { ProductFilters } from '@/lib/api';

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

const PER_PAGE = 24;

export default function BrandPage() {
  const { slug } = useParams<{ slug: string }>();
  const [search, setSearch] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);

  const filters: Omit<ProductFilters, 'brand'> = useMemo(
    () => ({
      search: search || undefined,
      verified_only: verifiedOnly || undefined,
      category: category || undefined,
      page,
      per_page: PER_PAGE,
    }),
    [search, verifiedOnly, category, page]
  );

  const { data: coverage, loading: coverageLoading, error: coverageError } = useAPI(
    () => getBrandCoverage(slug!),
    [slug]
  );

  const { data: productsResponse, loading: productsLoading, error: productsError } = useAPI(
    () => getBrandProducts(slug!, filters),
    [slug, search, verifiedOnly, category, page]
  );

  const products = productsResponse?.items ?? [];
  const total = productsResponse?.total ?? 0;
  const totalPages = Math.ceil(total / PER_PAGE);

  // Compute seal breakdown from current page products (visible context)
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

  // Unique categories from products for the dropdown
  const categories = useMemo(() => {
    const cats = new Set<string>();
    for (const p of products) {
      if (p.product_category) cats.add(p.product_category);
    }
    return Array.from(cats).sort();
  }, [products]);

  const handleSearch = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setPage(1);
  }, []);

  if (coverageLoading) return <LoadingState message="Loading brand..." />;
  if (coverageError) return <ErrorState message={coverageError} />;
  if (!coverage) return null;

  const inciPercent = Math.round(coverage.verified_inci_rate * 100);

  return (
    <div className="space-y-8">
      {/* Breadcrumb */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="flex items-center gap-2 text-sm text-ink-muted mb-1">
          <Link to="/" className="hover:text-ink transition-colors">Home</Link>
          <span>/</span>
          <Link to="/brands" className="hover:text-ink transition-colors">Brands</Link>
          <span>/</span>
          <span className="text-ink font-medium">{formatBrandName(slug!)}</span>
        </div>
      </motion.div>

      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.05 }}
        className="flex flex-col sm:flex-row sm:items-center gap-4"
      >
        <div className="flex-1">
          <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
            {formatBrandName(slug!)}
          </h1>
          <div className="flex items-center gap-3 mt-2">
            <Badge variant="outline" className="text-xs">
              {coverage.status}
            </Badge>
            <span className="text-sm text-ink-muted">
              {coverage.extracted_total} products
            </span>
            <span className="text-sm text-ink-muted">
              {inciPercent}% INCI verified
            </span>
          </div>
        </div>
      </motion.div>

      {/* Stats Row */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        <Card>
          <CardContent className="pt-2">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Products</p>
            <p className="text-2xl font-display font-semibold">{coverage.extracted_total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-2">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">INCI Rate</p>
            <p className="text-2xl font-display font-semibold">{inciPercent}%</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-2">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Verified</p>
            <p className="text-2xl font-display font-semibold text-emerald-600">{coverage.verified_inci_total}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-2">
            <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">Quarantined</p>
            <p className="text-2xl font-display font-semibold text-red-500">{coverage.quarantined_total}</p>
          </CardContent>
        </Card>
      </motion.div>

      {/* Seal Breakdown */}
      {sealBreakdown.length > 0 && (
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.15 }}
          className="flex flex-wrap gap-2"
        >
          {sealBreakdown.map(([seal, count]) => (
            <span key={seal} className="flex items-center gap-1">
              <SealBadge seal={seal} />
              <span className="text-xs text-muted-foreground">{count}</span>
            </span>
          ))}
        </motion.div>
      )}

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="flex flex-col sm:flex-row gap-3"
      >
        {/* Search */}
        <div className="relative flex-1">
          <svg
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
            width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search products..."
            value={search}
            onChange={handleSearch}
            className="w-full rounded-lg border border-ink/10 bg-white pl-10 pr-4 py-2 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-champagne/40 focus:border-champagne"
          />
        </div>

        {/* Verified Only Toggle */}
        <button
          onClick={() => { setVerifiedOnly(!verifiedOnly); setPage(1); }}
          className={`px-4 py-2 rounded-lg border text-sm transition-colors ${
            verifiedOnly
              ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
              : 'bg-white border-ink/10 text-ink-muted hover:text-ink'
          }`}
        >
          Verified Only
        </button>

        {/* Category Dropdown */}
        {categories.length > 0 && (
          <select
            value={category}
            onChange={(e) => { setCategory(e.target.value); setPage(1); }}
            className="rounded-lg border border-ink/10 bg-white px-4 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-champagne/40"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </option>
            ))}
          </select>
        )}
      </motion.div>

      {/* Product Grid */}
      {productsLoading ? (
        <LoadingState message="Loading products..." />
      ) : productsError ? (
        <ErrorState message={productsError} />
      ) : products.length === 0 ? (
        <EmptyState title="No products found" description="Try adjusting your filters." />
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.25 }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {products.map((product, i) => (
              <motion.div
                key={product.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: 0.02 * i }}
              >
                <ProductCard product={product} brandSlug={slug!} />
              </motion.div>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 mt-8">
              <button
                disabled={page <= 1}
                onClick={() => setPage(page - 1)}
                className="px-3 py-1.5 rounded-lg border border-ink/10 text-sm text-ink-muted hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Previous
              </button>
              <span className="text-sm text-ink-muted">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(page + 1)}
                className="px-3 py-1.5 rounded-lg border border-ink/10 text-sm text-ink-muted hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Next
              </button>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}
