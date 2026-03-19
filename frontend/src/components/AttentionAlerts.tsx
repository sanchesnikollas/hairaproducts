import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { getQuarantine } from '@/lib/api';
import type { QuarantineItem } from '@/types/api';

interface BrandData {
  brand_slug: string;
  brand_name: string;
  product_count: number;
  inci_rate: number;
}

interface AttentionAlertsProps {
  brands: BrandData[];
}

export default function AttentionAlerts({ brands }: AttentionAlertsProps) {
  const [quarantineItems, setQuarantineItems] = useState<QuarantineItem[]>([]);

  useEffect(() => {
    getQuarantine('pending')
      .then(setQuarantineItems)
      .catch(() => {});
  }, []);

  const totalQuarantine = quarantineItems.length;

  // Brands with <50% INCI
  const lowInciBrands = brands.filter((b) => b.inci_rate < 0.5);

  // Per-brand quarantine counts
  const quarantineByBrand: Record<string, number> = {};
  for (const item of quarantineItems) {
    const slug = item.brand_slug ?? 'unknown';
    quarantineByBrand[slug] = (quarantineByBrand[slug] || 0) + 1;
  }

  // Per-brand missing INCI counts
  const brandsWithGaps = brands
    .map((b) => ({
      ...b,
      missing_inci: Math.round(b.product_count * (1 - b.inci_rate)),
    }))
    .filter((b) => b.missing_inci > 5)
    .sort((a, b) => b.missing_inci - a.missing_inci)
    .slice(0, 3);

  const hasAlerts = totalQuarantine > 0 || lowInciBrands.length > 0 || brandsWithGaps.length > 0;

  if (!hasAlerts) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex items-center gap-2 py-2.5 px-4 rounded-lg bg-emerald-50/50 border border-emerald-100 text-emerald-600 text-sm"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Base saudavel — nenhum alerta
      </motion.div>
    );
  }

  // Find first brand with quarantine items for the link
  const firstQuarantineBrand = Object.keys(quarantineByBrand)[0];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.4 }}
      className="flex flex-wrap gap-2"
    >
      {totalQuarantine > 0 && firstQuarantineBrand && (
        <Link to={`/brands/${firstQuarantineBrand}?tab=quarentena`}>
          <span className="inline-flex items-center cursor-pointer text-xs font-medium px-3 py-1.5 rounded-lg bg-red-50 text-red-600 border border-red-100 hover:bg-red-100 transition-colors">
            {totalQuarantine} em quarentena
          </span>
        </Link>
      )}

      {lowInciBrands.length > 0 && (
        <Link to="/brands">
          <span className="inline-flex items-center cursor-pointer text-xs font-medium px-3 py-1.5 rounded-lg bg-amber-50 text-amber-700 border border-amber-100 hover:bg-amber-100 transition-colors">
            {lowInciBrands.length} marcas &lt;50% INCI
          </span>
        </Link>
      )}

      {brandsWithGaps.map((b) => (
        <Link key={b.brand_slug} to={`/brands/${b.brand_slug}`}>
          <span className="inline-flex items-center cursor-pointer text-xs font-medium px-3 py-1.5 rounded-lg bg-neutral-50 text-neutral-600 border border-neutral-200 hover:bg-neutral-100 transition-colors">
            {b.brand_name}: {b.missing_inci} sem INCI
          </span>
        </Link>
      ))}
    </motion.div>
  );
}
