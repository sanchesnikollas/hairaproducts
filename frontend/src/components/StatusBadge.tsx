import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

type StatusConfig = {
  variant: 'secondary' | 'outline' | 'destructive';
  label: string;
  className?: string;
};

const statusConfig: Record<string, StatusConfig> = {
  verified_inci: { variant: 'secondary', label: 'Verified INCI' },
  catalog_only: { variant: 'outline', label: 'Catalog Only', className: 'border-amber/30 bg-amber-bg text-amber' },
  quarantined: { variant: 'destructive', label: 'Quarantined' },
  done: { variant: 'secondary', label: 'Done' },
  pending: { variant: 'outline', label: 'Pending', className: 'border-amber/30 bg-amber-bg text-amber' },
  running: { variant: 'outline', label: 'Running', className: 'border-champagne/30 bg-champagne-light/20 text-champagne-dark' },
  approved: { variant: 'secondary', label: 'Approved' },
  rejected: { variant: 'destructive', label: 'Rejected' },
  pending_review: { variant: 'outline', label: 'Pending Review', className: 'border-amber/30 bg-amber-bg text-amber' },
};

const fallbackConfig: StatusConfig = {
  variant: 'outline',
  label: '',
  className: 'border-ink/10 text-ink-muted',
};

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const config = statusConfig[status] ?? { ...fallbackConfig, label: status };

  const sizeClasses = size === 'sm'
    ? 'text-[11px] h-auto px-2.5 py-0.5'
    : 'text-xs h-auto px-3 py-1';

  return (
    <Badge
      variant={config.variant}
      className={cn(
        'tracking-wide uppercase font-medium',
        sizeClasses,
        config.className,
      )}
    >
      {config.label}
    </Badge>
  );
}
