interface ProgressBarProps {
  value: number; // 0-1
  label?: string;
  showPercent?: boolean;
  color?: 'sage' | 'champagne' | 'coral' | 'amber';
  height?: 'sm' | 'md';
}

const colorMap = {
  sage: 'bg-sage',
  champagne: 'bg-champagne',
  coral: 'bg-coral',
  amber: 'bg-amber',
};

const trackMap = {
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
  const barHeight = height === 'sm' ? 'h-1.5' : 'h-2.5';

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
      <div className={`w-full ${barHeight} rounded-full ${trackMap[color]} overflow-hidden`}>
        <div
          className={`${barHeight} rounded-full ${colorMap[color]} progress-bar-animated`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
