interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { bg: string; text: string; label: string }> = {
  verified_inci: { bg: 'bg-sage-bg', text: 'text-sage', label: 'Verified INCI' },
  catalog_only: { bg: 'bg-amber-bg', text: 'text-amber', label: 'Catalog Only' },
  quarantined: { bg: 'bg-coral-bg', text: 'text-coral', label: 'Quarantined' },
  done: { bg: 'bg-sage-bg', text: 'text-sage', label: 'Done' },
  pending: { bg: 'bg-amber-bg', text: 'text-amber', label: 'Pending' },
  running: { bg: 'bg-champagne/10', text: 'text-champagne-dark', label: 'Running' },
  approved: { bg: 'bg-sage-bg', text: 'text-sage', label: 'Approved' },
  rejected: { bg: 'bg-coral-bg', text: 'text-coral', label: 'Rejected' },
  pending_review: { bg: 'bg-amber-bg', text: 'text-amber', label: 'Pending Review' },
};

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const config = statusConfig[status] ?? {
    bg: 'bg-ink/5',
    text: 'text-ink-muted',
    label: status,
  };

  const sizeClasses = size === 'sm' ? 'text-[11px] px-2.5 py-0.5' : 'text-xs px-3 py-1';

  return (
    <span
      className={`inline-flex items-center rounded-full font-medium tracking-wide uppercase ${config.bg} ${config.text} ${sizeClasses}`}
    >
      {config.label}
    </span>
  );
}
