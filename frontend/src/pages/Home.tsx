import { motion } from 'motion/react';
import { Card, CardContent } from '@/components/ui/card';
import BrandCard from '@/components/BrandCard';
import LoadingState, { ErrorState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getGlobalStats, getBrands } from '@/lib/api';
import type { BrandCoverage, BrandSummary, GlobalStats } from '@/types/api';

type BrandItem = BrandCoverage | BrandSummary;

function isBrandSummary(b: BrandItem): b is BrandSummary {
  return 'brand_name' in b;
}

function getBrandName(b: BrandItem): string {
  if (isBrandSummary(b)) return b.brand_name;
  return b.brand_slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function getBrandProductCount(b: BrandItem): number {
  if (isBrandSummary(b)) return b.product_count;
  return (b as BrandCoverage).extracted_total;
}

function getBrandInciRate(b: BrandItem): number {
  if (isBrandSummary(b)) return b.inci_rate;
  return (b as BrandCoverage).verified_inci_rate;
}

function getBrandPlatform(b: BrandItem): string | null {
  if (isBrandSummary(b)) return b.platform;
  return null;
}

export default function Home() {
  const { data: stats, loading: statsLoading, error: statsError } = useAPI<GlobalStats>(getGlobalStats);
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI<BrandCoverage[]>(getBrands);

  const loading = statsLoading || brandsLoading;
  const error = statsError || brandsError;

  if (loading) return <LoadingState message="Loading HAIRA..." />;
  if (error) return <ErrorState message={error} />;

  const statCards = [
    { label: 'Total Products', value: stats?.total_products ?? 0 },
    { label: 'Total Brands', value: stats?.total_brands ?? 0 },
    { label: 'Avg INCI Rate', value: `${Math.round((stats?.avg_inci_rate ?? 0) * 100)}%` },
    { label: 'Platforms', value: stats?.platforms?.length ?? 0 },
  ];

  return (
    <div className="space-y-12">
      {/* Hero */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center pt-8 pb-4"
      >
        <h1 className="font-display text-5xl font-bold tracking-tight text-ink">HAIRA</h1>
        <p className="mt-3 text-lg text-ink-muted">
          Base de conhecimento de produtos capilares
        </p>
      </motion.div>

      {/* Stats Grid */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.15 }}
        className="grid grid-cols-2 md:grid-cols-4 gap-4"
      >
        {statCards.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 + i * 0.07 }}
          >
            <Card>
              <CardContent className="pt-2">
                <p className="text-xs uppercase tracking-wider text-muted-foreground mb-1">
                  {stat.label}
                </p>
                <p className="text-2xl font-display font-semibold text-card-foreground">
                  {typeof stat.value === 'number' ? stat.value.toLocaleString() : stat.value}
                </p>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </motion.div>

      {/* Brand Grid */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.35 }}
      >
        <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
          Brands
        </h2>
        {brands && brands.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {brands.map((brand, i) => (
              <motion.div
                key={brand.brand_slug}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.4 + i * 0.04 }}
              >
                <BrandCard
                  slug={brand.brand_slug}
                  name={getBrandName(brand)}
                  productCount={getBrandProductCount(brand)}
                  inciRate={getBrandInciRate(brand)}
                  platform={getBrandPlatform(brand)}
                />
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-faint">No brands found.</p>
        )}
      </motion.div>
    </div>
  );
}
