import { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { ArrowUpDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { getProducts, getFocusBrand } from '@/lib/api';
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
import { ErrorState, EmptyState } from '@/components/LoadingState';
import ProductFilters, { type StatusFilter } from '@/components/products/ProductFilters';
import ProductSheet from '@/components/products/ProductSheet';
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
  const [focusBrand, setFocusBrand] = useState<string | null>(null);
  const brandFilter = searchParams.get('brand') ?? '';

  // Pagination
  const [page, setPage] = useState(1);

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>('product_name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  // Sheet
  const [selectedProductId, setSelectedProductId] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  // Debounce search
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  useEffect(() => {
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(debounceRef.current);
  }, [search]);

  // Focus brand
  useEffect(() => {
    getFocusBrand()
      .then(({ focus_brand }) => {
        if (focus_brand) setFocusBrand(focus_brand);
      })
      .catch(() => {});
  }, []);

  // Reset page when filters change
  useEffect(() => {
    setPage(1);
  }, [status, category, excludeKits, verifiedOnly]);

  // Fetch products
  const fetcher = useCallback(
    () =>
      getProducts({
        brand: brandFilter || undefined,
        verified_only: verifiedOnly || (status === 'verified_inci') || undefined,
        exclude_kits: excludeKits || undefined,
        search: debouncedSearch || undefined,
        category: category || undefined,
        page,
        per_page: PER_PAGE,
      }),
    [brandFilter, verifiedOnly, excludeKits, debouncedSearch, category, page, status]
  );

  const { data: response, loading, error, refetch } = useAPI(
    fetcher,
    [brandFilter, verifiedOnly, excludeKits, debouncedSearch, category, page, status]
  );

  const products = response?.items ?? [];
  const totalProducts = response?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalProducts / PER_PAGE));

  // Filter by status client-side (API may not support status filter directly)
  const filteredProducts = useMemo(() => {
    if (status === 'all') return products;
    return products.filter((p) => p.verification_status === status);
  }, [products, status]);

  // Status counts from current page data
  const statusCounts = useMemo(
    () => ({
      all: products.length,
      verified_inci: products.filter((p) => p.verification_status === 'verified_inci').length,
      catalog_only: products.filter((p) => p.verification_status === 'catalog_only').length,
      quarantined: products.filter((p) => p.verification_status === 'quarantined').length,
    }),
    [products]
  );

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
    const sorted = [...filteredProducts];
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
  }, [filteredProducts, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const handleRowClick = (product: Product) => {
    setSelectedProductId(product.id);
    setSheetOpen(true);
  };

  // Pagination info
  const startItem = (page - 1) * PER_PAGE + 1;
  const endItem = Math.min(page * PER_PAGE, totalProducts);

  if (error) return <ErrorState message={error} onRetry={refetch} />;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-3"
      >
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
          Products
        </h1>
        <Badge variant="secondary" className="text-sm tabular-nums">
          {totalProducts}
        </Badge>
        {focusBrand && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-champagne/10 text-champagne-dark border border-champagne/15">
            <span className="w-1.5 h-1.5 rounded-full bg-champagne" />
            {formatBrandName(focusBrand)}
          </span>
        )}
      </motion.div>

      {/* Filters */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <ProductFilters
          status={status}
          onStatusChange={setStatus}
          search={search}
          onSearchChange={setSearch}
          category={category}
          onCategoryChange={setCategory}
          excludeKits={excludeKits}
          onExcludeKitsChange={setExcludeKits}
          verifiedOnly={verifiedOnly}
          onVerifiedOnlyChange={setVerifiedOnly}
          categories={categories}
          statusCounts={statusCounts}
        />
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <div className="rounded-xl border border-ink/8 bg-white overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[52px]" />
                <TableHead>
                  <SortableHeader
                    label="Product Name"
                    sortKey="product_name"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead>
                  <SortableHeader
                    label="Category"
                    sortKey="product_category"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead>
                  <SortableHeader
                    label="Status"
                    sortKey="verification_status"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="text-right">
                  <SortableHeader
                    label="INCI"
                    sortKey="inci_count"
                    currentKey={sortKey}
                    currentDir={sortDir}
                    onClick={handleSort}
                  />
                </TableHead>
                <TableHead className="text-right">
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
                ? Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={i}>
                      <TableCell>
                        <Skeleton className="h-10 w-10 rounded-md" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-48" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-24" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-5 w-20 rounded-full" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-8 ml-auto" />
                      </TableCell>
                      <TableCell>
                        <Skeleton className="h-4 w-8 ml-auto" />
                      </TableCell>
                    </TableRow>
                  ))
                : sortedProducts.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={6} className="h-32">
                        <EmptyState
                          title="No products found"
                          description="Try adjusting your filters"
                        />
                      </TableCell>
                    </TableRow>
                  )
                  : sortedProducts.map((product) => {
                      const score = product.quality?.score;
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
                          className="cursor-pointer hover:bg-cream-dark/30 transition-colors"
                          onClick={() => handleRowClick(product)}
                        >
                          <TableCell>
                            {product.image_url_main ? (
                              <img
                                src={product.image_url_main}
                                alt=""
                                className="h-10 w-10 rounded-md object-cover bg-cream"
                                onError={(e) => {
                                  (e.target as HTMLImageElement).style.display = 'none';
                                }}
                              />
                            ) : (
                              <div className="h-10 w-10 rounded-md bg-cream flex items-center justify-center text-ink-faint text-xs">
                                --
                              </div>
                            )}
                          </TableCell>
                          <TableCell className="max-w-[300px]">
                            <span className="font-medium text-ink truncate block">
                              {sanitizeText(product.product_name)}
                            </span>
                          </TableCell>
                          <TableCell className="text-ink-muted">
                            {product.product_category ?? '--'}
                          </TableCell>
                          <TableCell>
                            <StatusBadge status={product.verification_status} />
                          </TableCell>
                          <TableCell className="text-right tabular-nums text-ink-muted">
                            {product.inci_ingredients?.length ?? 0}
                          </TableCell>
                          <TableCell className={`text-right tabular-nums font-medium ${scoreColor}`}>
                            {score ?? '--'}
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

      {/* Product Detail Sheet */}
      <ProductSheet
        productId={selectedProductId}
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        onProductUpdated={refetch}
      />
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
