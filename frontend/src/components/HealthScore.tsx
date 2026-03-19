import { motion } from 'motion/react';

interface HealthScoreProps {
  score: number;
  totalProducts: number;
  totalBrands: number;
  totalVerified: number;
  totalQuarantine: number;
}

function getScoreColor(score: number): string {
  if (score >= 80) return 'text-emerald-600';
  if (score >= 50) return 'text-amber-600';
  return 'text-red-500';
}

function getBarColor(score: number): string {
  if (score >= 80) return 'bg-emerald-500';
  if (score >= 50) return 'bg-amber-400';
  return 'bg-red-400';
}

export default function HealthScore({ score, totalProducts, totalBrands, totalVerified, totalQuarantine }: HealthScoreProps) {
  const scoreColor = getScoreColor(score);
  const roundedScore = Math.round(score);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      <div className="bg-white rounded-xl border border-neutral-200/60 shadow-sm">
        <div className="p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-wider text-neutral-400 mb-1">
                INCI Coverage
              </p>
              <div className="flex items-baseline gap-1">
                <span className={`text-4xl font-semibold tabular-nums ${scoreColor}`}>
                  {roundedScore}
                </span>
                <span className={`text-lg font-medium ${scoreColor}`}>%</span>
              </div>
              <div className="mt-2.5 h-1 w-32 rounded-full bg-neutral-100 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${getBarColor(score)}`}
                  style={{ width: `${roundedScore}%` }}
                />
              </div>
            </div>

            <div className="flex gap-8">
              <Stat label="Produtos" value={totalProducts.toLocaleString()} />
              <Stat label="Marcas" value={String(totalBrands)} />
              <Stat label="Verificados" value={totalVerified.toLocaleString()} color="text-emerald-600" />
              <Stat
                label="Quarentena"
                value={String(totalQuarantine)}
                color={totalQuarantine > 0 ? 'text-red-500' : undefined}
              />
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="text-right">
      <p className="text-[11px] uppercase tracking-wider text-neutral-400 font-medium">{label}</p>
      <p className={`text-lg font-semibold tabular-nums mt-0.5 ${color ?? 'text-neutral-800'}`}>
        {value}
      </p>
    </div>
  );
}
