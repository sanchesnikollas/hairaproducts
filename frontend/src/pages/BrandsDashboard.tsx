import { useState, useMemo } from 'react';
import { motion } from 'motion/react';
import { getBrands } from '../lib/api';
import { useAPI } from '../hooks/useAPI';
import type { BrandCoverage } from '../types/api';
import ProgressBar from '../components/ProgressBar';
import StatusBadge from '../components/StatusBadge';
import LoadingState, { ErrorState, EmptyState } from '../components/LoadingState';

type SortField = 'brand_slug' | 'verified_inci_rate' | 'extracted_total' | 'discovered_total';
type SortDir = 'asc' | 'desc';

export default function BrandsDashboard() {
  const { data: brands, loading, error, refetch } = useAPI(getBrands);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('verified_inci_rate');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const filtered = useMemo(() => {
    if (!brands) return [];
    let result = brands.filter((b) =>
      b.brand_slug.toLowerCase().includes(search.toLowerCase())
    );
    result.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDir === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDir === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
    return result;
  }, [brands, search, sortField, sortDir]);

  const stats = useMemo(() => {
    if (!brands || brands.length === 0) return null;
    const totalBrands = brands.length;
    const totalProducts = brands.reduce((s, b) => s + b.extracted_total, 0);
    const totalVerified = brands.reduce((s, b) => s + b.verified_inci_total, 0);
    const avgRate = totalProducts > 0 ? totalVerified / totalProducts : 0;
    return { totalBrands, totalProducts, totalVerified, avgRate };
  }, [brands]);

  function toggleSort(field: SortField) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  function sortIndicator(field: SortField) {
    if (sortField !== field) return '';
    return sortDir === 'asc' ? ' \u2191' : ' \u2193';
  }

  if (loading) return <LoadingState message="Loading brand coverage..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;
  if (!brands || brands.length === 0) return <EmptyState title="No brands found" description="Run the pipeline to generate brand coverage data." />;

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
          Brand Coverage
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          Monitoring INCI verification progress across all registered brands.
        </p>
      </motion.div>

      {/* Stats Cards */}
      {stats && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="grid grid-cols-4 gap-4"
        >
          <StatCard label="Brands Tracked" value={stats.totalBrands} />
          <StatCard label="Products Extracted" value={stats.totalProducts} />
          <StatCard label="Verified INCI" value={stats.totalVerified} accent />
          <StatCard label="Avg. Verification Rate" value={`${Math.round(stats.avgRate * 100)}%`} accent />
        </motion.div>
      )}

      {/* Search */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <div className="relative max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            type="text"
            placeholder="Search brands..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-ink/8 rounded-xl text-sm placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-champagne/30 focus:border-champagne/40 transition-all"
          />
        </div>
      </motion.div>

      {/* Table */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.25 }}
        className="bg-white rounded-2xl border border-ink/5 overflow-hidden shadow-sm"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-ink/5">
                <Th onClick={() => toggleSort('brand_slug')}>Brand{sortIndicator('brand_slug')}</Th>
                <Th align="center">Status</Th>
                <Th align="right" onClick={() => toggleSort('discovered_total')}>Discovered{sortIndicator('discovered_total')}</Th>
                <Th align="right" onClick={() => toggleSort('extracted_total')}>Extracted{sortIndicator('extracted_total')}</Th>
                <Th onClick={() => toggleSort('verified_inci_rate')} className="min-w-[200px]">
                  Verification Rate{sortIndicator('verified_inci_rate')}
                </Th>
                <Th align="right">Quarantined</Th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((brand, i) => (
                <BrandRow key={brand.brand_slug} brand={brand} index={i} />
              ))}
            </tbody>
          </table>
        </div>
        {filtered.length === 0 && (
          <div className="py-12 text-center text-sm text-ink-muted">
            No brands match your search.
          </div>
        )}
      </motion.div>
    </div>
  );
}

// ── Sub-components ──

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: boolean }) {
  return (
    <div className="bg-white rounded-xl border border-ink/5 p-5 shadow-sm">
      <p className="text-xs uppercase tracking-wider text-ink-muted mb-1">{label}</p>
      <p className={`text-2xl font-display font-semibold ${accent ? 'text-champagne-dark' : 'text-ink'}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

function Th({
  children,
  align = 'left',
  onClick,
  className = '',
}: {
  children: React.ReactNode;
  align?: 'left' | 'center' | 'right';
  onClick?: () => void;
  className?: string;
}) {
  const alignClass = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';
  return (
    <th
      onClick={onClick}
      className={`px-5 py-3.5 text-[11px] uppercase tracking-wider font-semibold text-ink-muted ${alignClass} ${onClick ? 'cursor-pointer hover:text-ink transition-colors select-none' : ''} ${className}`}
    >
      {children}
    </th>
  );
}

function BrandRow({ brand, index }: { brand: BrandCoverage; index: number }) {
  const rateColor = brand.verified_inci_rate >= 0.8 ? 'sage' : brand.verified_inci_rate >= 0.5 ? 'champagne' : 'coral';

  return (
    <motion.tr
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3, delay: index * 0.02 }}
      className="border-b border-ink/3 last:border-b-0 hover:bg-cream/50 transition-colors"
    >
      <td className="px-5 py-4">
        <span className="text-sm font-medium text-ink">{brand.brand_slug}</span>
      </td>
      <td className="px-5 py-4 text-center">
        <StatusBadge status={brand.status} />
      </td>
      <td className="px-5 py-4 text-right text-sm tabular-nums text-ink-light">
        {brand.discovered_total.toLocaleString()}
      </td>
      <td className="px-5 py-4 text-right text-sm tabular-nums text-ink-light">
        {brand.extracted_total.toLocaleString()}
      </td>
      <td className="px-5 py-4">
        <ProgressBar value={brand.verified_inci_rate} color={rateColor} />
      </td>
      <td className="px-5 py-4 text-right">
        {brand.quarantined_total > 0 ? (
          <span className="inline-flex items-center justify-center min-w-[24px] h-6 px-2 rounded-full bg-coral-bg text-coral text-xs font-medium">
            {brand.quarantined_total}
          </span>
        ) : (
          <span className="text-sm text-ink-faint">&mdash;</span>
        )}
      </td>
    </motion.tr>
  );
}
