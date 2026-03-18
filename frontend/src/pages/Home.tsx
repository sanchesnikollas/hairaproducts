import { useMemo } from 'react';
import { motion } from 'motion/react';
import BrandCard from '@/components/BrandCard';
import HealthScore from '@/components/HealthScore';
import AttentionAlerts from '@/components/AttentionAlerts';
import LoadingState, { ErrorState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getBrands, getQuarantine } from '@/lib/api';
import type { BrandCoverage, BrandSummary, QuarantineItem } from '@/types/api';

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
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI<BrandCoverage[]>(getBrands);
  const { data: quarantineItems } = useAPI<QuarantineItem[]>(() => getQuarantine('pending'));

  const computed = useMemo(() => {
    if (!brands) return null;
    const totalProducts = brands.reduce((sum, b) => sum + getBrandProductCount(b), 0);
    const weightedSum = brands.reduce(
      (sum, b) => sum + getBrandInciRate(b) * getBrandProductCount(b), 0
    );
    const healthScore = totalProducts > 0 ? (weightedSum / totalProducts) * 100 : 0;
    const totalVerified = brands.reduce((sum, b) => {
      if (isBrandSummary(b)) return sum + Math.round(b.product_count * b.inci_rate);
      return sum + (b as BrandCoverage).verified_inci_total;
    }, 0);

    const quarantineByBrand: Record<string, number> = {};
    for (const item of quarantineItems ?? []) {
      const slug = item.brand_slug ?? 'unknown';
      quarantineByBrand[slug] = (quarantineByBrand[slug] || 0) + 1;
    }

    const sortedBrands = [...brands].sort((a, b) => {
      const aQ = quarantineByBrand[a.brand_slug] ?? 0;
      const bQ = quarantineByBrand[b.brand_slug] ?? 0;
      if (aQ !== bQ) return bQ - aQ;
      return getBrandInciRate(a) - getBrandInciRate(b);
    });

    const alertBrands = brands.map((b) => ({
      brand_slug: b.brand_slug,
      brand_name: getBrandName(b),
      product_count: getBrandProductCount(b),
      inci_rate: getBrandInciRate(b),
    }));

    return { totalProducts, healthScore, totalVerified, quarantineByBrand, sortedBrands, alertBrands };
  }, [brands, quarantineItems]);

  if (brandsLoading) return <LoadingState message="Loading HAIRA..." />;
  if (brandsError) return <ErrorState message={brandsError} />;
  if (!brands || !computed) return null;

  return (
    <div className="space-y-6">
      <HealthScore
        score={computed.healthScore}
        totalProducts={computed.totalProducts}
        totalBrands={brands.length}
        totalVerified={computed.totalVerified}
        totalQuarantine={(quarantineItems ?? []).length}
      />

      <AttentionAlerts brands={computed.alertBrands} />

      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[12px] uppercase tracking-wider text-neutral-400 font-semibold">
            Marcas
          </h2>
          <span className="text-xs text-neutral-400">{brands.length} marcas</span>
        </div>
        {computed.sortedBrands.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3">
            {computed.sortedBrands.map((brand, i) => (
              <motion.div
                key={brand.brand_slug}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25, delay: 0.2 + i * 0.03 }}
              >
                <BrandCard
                  slug={brand.brand_slug}
                  name={getBrandName(brand)}
                  productCount={getBrandProductCount(brand)}
                  inciRate={getBrandInciRate(brand)}
                  platform={getBrandPlatform(brand)}
                  quarantineCount={computed.quarantineByBrand[brand.brand_slug] ?? 0}
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
