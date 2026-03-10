import { cn } from '@/lib/utils';

interface ProgressBarProps {
  value: number; // 0-1
  label?: string;
  showPercent?: boolean;
  color?: 'sage' | 'champagne' | 'coral' | 'amber';
  height?: 'sm' | 'md';
}

const colorMap: Record<string, string> = {
  sage: 'bg-sage',
  champagne: 'bg-champagne',
  coral: 'bg-coral',
  amber: 'bg-amber',
};

const trackMap: Record<string, string> = {
  sage: 'bg-sage-light/40',
  champagne: 'bg-champagne-light/40',
  coral: 'bg-coral-light/40',
  amber: 'bg-amber-light/40',
};

export default function ProgressBar({
  value,
  label,
  showPercent = true,
  color = 'sage',
  height = 'sm',
}: ProgressBarProps) {
  const pct = Math.round(value * 100);

  return (
    <div className="flex flex-col gap-1">
      {(label || showPercent) && (
        <div className="flex items-center justify-between">
          {label && <span className="text-xs text-ink-muted">{label}</span>}
          {showPercent && (
            <span className="text-xs font-medium tabular-nums text-ink-light">
              {pct}%
            </span>
          )}
        </div>
      )}
      <div
        className={cn(
          'w-full rounded-full overflow-hidden',
          height === 'sm' ? 'h-1.5' : 'h-2.5',
          trackMap[color],
        )}
      >
        <div
          className={cn(
            'rounded-full progress-bar-animated',
            height === 'sm' ? 'h-1.5' : 'h-2.5',
            colorMap[color],
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
