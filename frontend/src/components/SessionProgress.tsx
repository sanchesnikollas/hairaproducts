import { motion } from 'motion/react';

interface SessionProgressProps {
  reviewed: number;
  total: number;
}

export default function SessionProgress({ reviewed, total }: SessionProgressProps) {
  if (total === 0) return null;

  const allDone = reviewed >= total;
  const percent = Math.round((reviewed / total) * 100);

  if (allDone) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center py-2 text-sm text-emerald-600"
      >
        <svg className="inline-block mr-1.5 -mt-0.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Tudo revisado
      </motion.div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>{reviewed}/{total} revisados</span>
        <span>{percent}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-ink/5 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-champagne"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>
    </div>
  );
}
