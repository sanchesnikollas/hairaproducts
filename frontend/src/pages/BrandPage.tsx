import { useState, useMemo, useCallback } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import ProductCard from '@/components/ProductCard';
import QuarantineTab from '@/components/QuarantineTab';
import CoverageTab from '@/components/CoverageTab';
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

function getInciColor(rate: number): string {
  if (rate >= 0.8) return 'text-emerald-600';
  if (rate >= 0.5) return 'text-amber-600';
  return 'text-red-600';
}

const PER_PAGE = 24;

export default function BrandPage() {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') ?? 'produtos';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [search, setSearch] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [quarantineCount, setQuarantineCount] = useState<number | null>(null);

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

  const products = useMemo(() => productsResponse?.items ?? [], [productsResponse]);
  const total = productsResponse?.total ?? 0;
  const totalPages = Math.ceil(total / PER_PAGE);

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

  function handleTabChange(value: string | number | null) {
    if (value && typeof value === 'string') {
      setActiveTab(value);
      setSearchParams(value === 'produtos' ? {} : { tab: value });
    }
  }

  if (coverageLoading) return <LoadingState message="Loading brand..." />;
  if (coverageError) return <ErrorState message={coverageError} />;
  if (!coverage) return null;

  const inciPercent = Math.round(coverage.verified_inci_rate * 100);
  const displayQuarantineCount = quarantineCount ?? coverage.quarantined_total;

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
        <div className="flex items-center gap-1.5 text-[13px] text-neutral-400">
          <Link to="/" className="hover:text-neutral-600 transition-colors">Home</Link>
          <span className="text-neutral-300">/</span>
          <Link to="/brands" className="hover:text-neutral-600 transition-colors">Brands</Link>
          <span className="text-neutral-300">/</span>
          <span className="text-neutral-700 font-medium">{formatBrandName(slug!)}</span>
        </div>
      </motion.div>

      {/* Compact Header */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.05 }}
        className="flex items-center gap-6"
      >
        <div className="flex-1 min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
            {formatBrandName(slug!)}
          </h1>
          <div className="flex items-center gap-2 mt-1.5 text-sm text-neutral-500">
            <span>{coverage.extracted_total} produtos</span>
            <span className="text-neutral-300">·</span>
            <span>{coverage.verified_inci_total} verificados</span>
            {displayQuarantineCount > 0 && (
              <>
                <span className="text-neutral-300">·</span>
                <span className="text-red-500 font-medium">{displayQuarantineCount} quarentena</span>
              </>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className={`text-4xl font-semibold tabular-nums ${getInciColor(coverage.verified_inci_rate)}`}>
            {inciPercent}%
          </p>
          <p className="text-[11px] text-neutral-400 uppercase tracking-wider mt-1 font-medium">INCI Coverage</p>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="produtos">Produtos</TabsTrigger>
            <TabsTrigger value="quarentena" className="gap-1.5">
              Quarentena
              {displayQuarantineCount > 0 && (
                <Badge variant="destructive" className="text-[10px] h-4 px-1.5 ml-1">
                  {displayQuarantineCount}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="cobertura">Cobertura</TabsTrigger>
          </TabsList>

          {/* Produtos Tab */}
          <TabsContent value="produtos">
            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-2 mt-4">
              <div className="relative flex-1">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400"
                  width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
                <input
                  type="text"
                  placeholder="Buscar produtos..."
                  value={search}
                  onChange={handleSearch}
                  className="w-full rounded-lg border border-neutral-200 bg-white pl-10 pr-4 py-2 text-sm text-neutral-800 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-neutral-900/10 focus:border-neutral-300 transition-colors"
                />
              </div>
              <button
                onClick={() => { setVerifiedOnly(!verifiedOnly); setPage(1); }}
                className={`px-4 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  verifiedOnly
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-white border-neutral-200 text-neutral-600 hover:bg-neutral-50'
                }`}
              >
                Apenas verificados
              </button>
              {categories.length > 0 && (
                <select
                  value={category}
                  onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                  className="rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-900/10 transition-colors"
                >
                  <option value="">Todas categorias</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Product Grid */}
            {productsLoading ? (
              <LoadingState message="Carregando produtos..." />
            ) : productsError ? (
              <ErrorState message={productsError} />
            ) : products.length === 0 ? (
              <EmptyState title="Nenhum produto encontrado" description="Tente ajustar os filtros." />
            ) : (
              <div className="mt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {products.map((product, i) => (
                    <motion.div
                      key={product.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.02 * i }}
                    >
                      <ProductCard
                        product={product}
                        brandSlug={slug!}
                      />
                    </motion.div>
                  ))}
                </div>

                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-3 mt-8">
                    <button
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                      className="px-3.5 py-1.5 rounded-lg border border-neutral-200 text-sm font-medium text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Anterior
                    </button>
                    <span className="text-sm text-neutral-400 tabular-nums">
                      {page} / {totalPages}
                    </span>
                    <button
                      disabled={page >= totalPages}
                      onClick={() => setPage(page + 1)}
                      className="px-3.5 py-1.5 rounded-lg border border-neutral-200 text-sm font-medium text-neutral-600 hover:bg-neutral-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      Proxima
                    </button>
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* Quarentena Tab */}
          <TabsContent value="quarentena">
            <QuarantineTab
              brandSlug={slug!}
              onCountChange={(count) => setQuarantineCount(count)}
            />
          </TabsContent>

          {/* Cobertura Tab */}
          <TabsContent value="cobertura">
            <CoverageTab coverage={coverage} />
          </TabsContent>
        </Tabs>
      </motion.div>

    </div>
  );
}
