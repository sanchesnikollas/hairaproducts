import { motion } from 'motion/react';
import type { BrandCoverage } from '@/types/api';

interface CoverageTabProps {
  coverage: BrandCoverage;
}

interface FunnelStep {
  label: string;
  count: number;
  color: string;
}

export default function CoverageTab({ coverage }: CoverageTabProps) {
  const steps: FunnelStep[] = [
    { label: 'Descobertos', count: coverage.discovered_total, color: 'bg-ink/20' },
    { label: 'Hair Products', count: coverage.hair_total, color: 'bg-blue-400' },
    { label: 'Extraidos', count: coverage.extracted_total, color: 'bg-amber-400' },
    { label: 'INCI Verificado', count: coverage.verified_inci_total, color: 'bg-emerald-500' },
  ];

  const maxCount = Math.max(...steps.map((s) => s.count), 1);

  return (
    <div className="py-4 space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-ink-faint font-semibold">
        Funil de Cobertura
      </h3>
      <div className="space-y-2">
        {steps.map((step, i) => {
          const widthPercent = Math.max((step.count / maxCount) * 100, 4);
          return (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08, duration: 0.3 }}
              className="flex items-center gap-3"
            >
              <span className="text-xs text-ink-muted w-28 shrink-0 text-right">
                {step.label}
              </span>
              <div className="flex-1 h-6 rounded bg-ink/[0.03] overflow-hidden">
                <motion.div
                  className={`h-full rounded ${step.color} flex items-center px-2`}
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPercent}%` }}
                  transition={{ delay: i * 0.08 + 0.15, duration: 0.5, ease: 'easeOut' }}
                >
                  <span className="text-xs font-medium text-white drop-shadow-sm">
                    {step.count.toLocaleString()}
                  </span>
                </motion.div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Summary stats */}
      <div className="flex items-center gap-4 pt-2 text-xs text-ink-muted border-t border-ink/5 mt-4">
        <span>Catalog Only: {coverage.catalog_only_total}</span>
        <span>Quarentena: {coverage.quarantined_total}</span>
        <span>Kits: {coverage.kits_total}</span>
        <span>Non-Hair: {coverage.non_hair_total}</span>
      </div>
    </div>
  );
}
