import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowUpDown, ChevronLeft, ChevronRight, Package } from 'lucide-react';
import { getProducts, getBrands } from '@/lib/api';
import type { BrandCoverage } from '@/types/api';
import { useAPI } from '@/hooks/useAPI';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import StatusBadge from '@/components/StatusBadge';
import { ErrorState } from '@/components/LoadingState';
import ProductFilters, { type StatusFilter } from '@/components/products/ProductFilters';
import type { Product } from '@/types/api';

const PER_PAGE = 50;

type SortKey = 'product_name' | 'product_category' | 'verification_status' | 'inci_count' | 'quality_score';
type SortDir = 'asc' | 'desc';

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

export default function ProductBrowser() {
  const [searchParams] = useSearchParams();

  // Filter state
  const [status, setStatus] = useState<StatusFilter>('all');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [category, setCategory] = useState('');
  const [excludeKits, setExcludeKits] = useState(true);
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [brandFilter, setBrandFilter] = useState(searchParams.get('brand') ?? '');

  // Fetch brands for the selector
  const { data: brandsData } = useAPI<BrandCoverage[]>(getBrands);

  // Pagination
  const [page, setPage] = useState(1);

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>('product_name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const navigate = useNavigate();

  // Debounce search
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Wrap filter setters to also reset page
  const handleStatusChange = useCallback((s: StatusFilter) => { setStatus(s); setPage(1); }, []);
  const handleCategoryChange = useCallback((c: string) => { setCategory(c); setPage(1); }, []);
  const handleExcludeKitsChange = useCallback((v: boolean) => { setExcludeKits(v); setPage(1); }, []);
  const handleVerifiedOnlyChange = useCallback((v: boolean) => { setVerifiedOnly(v); setPage(1); }, []);

  // Compute effective verified_only: true if filter is 'verified_inci' or toggle is on
  const effectiveVerifiedOnly = verifiedOnly || status === 'verified_inci';

  // Fetch products
  const fetcher = useCallback(
    () =>
      getProducts({
        brand: brandFilter || undefined,
        verified_only: effectiveVerifiedOnly || undefined,
        exclude_kits: excludeKits || undefined,
        search: debouncedSearch || undefined,
        category: category || undefined,
        page,
        per_page: PER_PAGE,
      }),
    [brandFilter, effectiveVerifiedOnly, excludeKits, debouncedSearch, category, page]
  );

  const { data: response, loading, error, refetch } = useAPI(
    fetcher,
    [brandFilter, effectiveVerifiedOnly, excludeKits, debouncedSearch, category, page]
  );

  const products = useMemo(() => response?.items ?? [], [response]);
  const totalProducts = response?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalProducts / PER_PAGE));

  // Categories from data
  const categories = useMemo(() => {
    const cats = new Set<string>();
    products.forEach((p) => {
      if (p.product_category) cats.add(p.product_category);
    });
    return [...cats].sort();
  }, [products]);

  // Sort
  const sortedProducts = useMemo(() => {
    const sorted = [...products];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case 'product_name':
          cmp = (a.product_name ?? '').localeCompare(b.product_name ?? '');
          break;
        case 'product_category':
          cmp = (a.product_category ?? '').localeCompare(b.product_category ?? '');
          break;
        case 'verification_status':
          cmp = a.verification_status.localeCompare(b.verification_status);
          break;
        case 'inci_count':
          cmp = (a.inci_ingredients?.length ?? 0) - (b.inci_ingredients?.length ?? 0);
          break;
        case 'quality_score':
          cmp = (a.quality?.score ?? 0) - (b.quality?.score ?? 0);
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [products, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const handleRowClick = (product: Product) => {
    navigate(`/ops/products/${product.id}`);
  };

  // Pagination info
  const startItem = (page - 1) * PER_PAGE + 1;
  const endItem = Math.min(page * PER_PAGE, totalProducts);

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-5">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-3"
      >
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Explorador
        </h1>
        <Badge variant="secondary" className="text-sm tabular-nums">
          {totalProducts}
        </Badge>
        <select
          value={brandFilter}
          onChange={(e) => { setBrandFilter(e.target.value); setPage(1); }}
          className="ml-auto rounded-lg border border-neutral-200 bg-white px-4 py-2 text-sm text-neutral-700 focus:outline-none focus:ring-2 focus:ring-neutral-900/10 transition-colors"
        >
          <option value="">Todas as marcas</option>
          {(brandsData ?? []).map((b) => (
            <option key={b.brand_slug} value={b.brand_slug}>
              {formatBrandName(b.brand_slug)}
            </option>
          ))}
        </select>
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <ProductFilters
          status={status}
          onStatusChange={handleStatusChange}
          search={search}
          onSearchChange={setSearch}
          category={category}
          onCategoryChange={handleCategoryChange}
          excludeKits={excludeKits}
          onExcludeKitsChange={handleExcludeKitsChange}
          verifiedOnly={verifiedOnly}
          onVerifiedOnlyChange={handleVerifiedOnlyChange}
          categories={categories}
          statusCounts={response?.status_counts ?? { all: totalProducts, verified_inci: 0, catalog_only: 0, quarantined: 0 }}
        />
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <div className="rounded-xl border border-neutral-200/60 bg-white shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent border-ink/8">
                <TableHead className="w-[56px] pl-4" />
                <TableHead className="min-w-[240px]">
                  <SortableHeader
                    label="Product Name"
                    sortKey="product_name"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="min-w-[120px]">
                  <SortableHeader
                    label="Category"
                    sortKey="product_category"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="min-w-[120px]">
                  <SortableHeader
                    label="Status"
                    sortKey="verification_status"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="text-right min-w-[80px]">
                  <SortableHeader
                    label="INCI"
                    sortKey="inci_count"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="text-right min-w-[80px] pr-4">
                  <SortableHeader
                    label="Quality"
                    sortKey="quality_score"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 10 }).map((_, i) => (
                    <TableRow key={i} className="border-ink/5">
                      <TableCell className="pl-4">
                        <Skeleton className="h-10 w-10 rounded-lg" />
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1.5">
                          <Skeleton className="h-4 w-52" />
                          <Skeleton className="h-3 w-24" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-20" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-20 rounded-full" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-8 ml-auto" />
                      </TableCell>
                      <TableCell className="pr-4">
                        <Skeleton className="h-4 w-8 ml-auto" />
                      </TableCell>
                    </TableRow>
                  ))
                : sortedProducts.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-48">
                        <div className="flex flex-col items-center justify-center gap-3 text-center">
                          <div className="rounded-full bg-cream p-3">
                            <Package className="size-6 text-ink-faint" />
                          </div>
                          <div>
                            <p className="text-sm font-medium text-ink">No products found</p>
                            <p className="text-xs text-ink-muted mt-1">Try adjusting your filters or search terms</p>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                  : sortedProducts.map((product) => {
                      const score = product.quality?.score;
                      const inciCount = product.inci_ingredients?.length ?? 0;
                      const scoreColor =
                        score === undefined
                          ? 'text-ink-faint'
                          : score === 100
                            ? 'text-sage'
                            : score >= 70
                              ? 'text-amber'
                              : 'text-coral';

                      return (
                        <TableRow
                          key={product.id}
                          className="cursor-pointer border-ink/5 hover:bg-cream/50 transition-colors group"
                          onClick={() => handleRowClick(product)}
                        >
                          <TableCell className="pl-4">
                            {product.image_url_main ? (
                              <img
                                src={product.image_url_main}
                                alt=""
                                className="h-10 w-10 rounded-lg object-cover bg-cream border border-ink/5"
                                loading="lazy"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none';
                                  (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                }}
                              />
                            ) : null}
                            <div className={`h-10 w-10 rounded-lg bg-cream-dark/50 flex items-center justify-center text-ink-faint ${product.image_url_main ? 'hidden' : ''}`}>
                              <Package className="size-4" />
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="min-w-0">
                              <span className="font-medium text-ink text-sm leading-tight line-clamp-2 group-hover:text-champagne-dark transition-colors">
                                {sanitizeText(product.product_name)}
                              </span>
                              {product.line_collection && (
                                <span className="text-xs text-ink-faint block mt-0.5 truncate">
                                  {product.line_collection}
                                </span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell className="text-sm text-ink-muted">
                            {product.product_category ?? '--'}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={product.verification_status} />
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-sm text-ink-muted">
                            {inciCount > 0 ? inciCount : '--'}
                          </TableCell>
                          <TableCell className={`text-right tabular-nums text-sm font-medium pr-4 ${scoreColor}`}>
                            {score !== undefined ? score : '--'}
                          </TableCell>
                        </TableRow>
                      );
                    })}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        {totalProducts > 0 && (
          <div className="flex items-center justify-between pt-4">
            <span className="text-sm text-ink-muted tabular-nums">
              Showing {startItem}–{endItem} of {totalProducts}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="size-4" />
                Previous
              </Button>
              <span className="text-sm text-ink-muted tabular-nums px-2">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </motion.div>

    </div>
  );
}

function SortableHeader({
  label,
  sortKey,
  currentKey,
  currentDir,
  onClick,
}: {
  label: string;
  sortKey: SortKey;
  currentKey: SortKey;
  currentDir: SortDir;
  onClick: (key: SortKey) => void;
}) {
  const active = currentKey === sortKey;
  return (
    <button
      className="inline-flex items-center gap-1 hover:text-ink transition-colors"
      onClick={() => onClick(sortKey)}
    >
      {label}
      <ArrowUpDown
        className={`size-3 ${active ? 'text-ink' : 'text-ink-faint'}`}
      />
      {active && (
        <span className="text-[10px] text-ink-faint">
          {currentDir === 'asc' ? '↑' : '↓'}
        </span>
      )}
    </button>
  );
}
