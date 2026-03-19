import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';

interface BrandCardProps {
  slug: string;
  name: string;
  productCount: number;
  inciRate: number;
  platform: string | null;
  quarantineCount?: number;
}

function getInciBarColor(rate: number): string {
  if (rate >= 0.9) return 'bg-emerald-500';
  if (rate >= 0.5) return 'bg-amber-400';
  return 'bg-red-400';
}

function getInciTextColor(rate: number): string {
  if (rate >= 0.9) return 'text-emerald-600';
  if (rate >= 0.5) return 'text-amber-600';
  return 'text-red-500';
}

const AVATAR_COLORS = [
  'bg-violet-100 text-violet-700',
  'bg-blue-100 text-blue-700',
  'bg-emerald-100 text-emerald-700',
  'bg-amber-100 text-amber-700',
  'bg-pink-100 text-pink-700',
  'bg-indigo-100 text-indigo-700',
  'bg-teal-100 text-teal-700',
  'bg-orange-100 text-orange-700',
];

function getAvatarColor(slug: string): string {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) & 0xffffffff;
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export default function BrandCard({ slug, name, productCount, inciRate, platform, quarantineCount = 0 }: BrandCardProps) {
  const inciPercent = Math.round(inciRate * 100);
  const avatarColor = getAvatarColor(slug);

  return (
    <Link to={`/brands/${slug}`} className="block group/brand-card">
      <div className="bg-white rounded-xl border border-neutral-200/60 p-4 transition-all duration-200 group-hover/brand-card:shadow-md group-hover/brand-card:border-neutral-300/60">
        <div className="flex items-center gap-3 mb-3">
          <div className="relative flex-shrink-0">
            <div
              className={cn(
                'w-9 h-9 rounded-lg flex items-center justify-center font-semibold text-sm',
                avatarColor
              )}
            >
              {name.charAt(0).toUpperCase()}
            </div>
            {quarantineCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-white" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-neutral-800 truncate">{name}</p>
            <p className="text-xs text-neutral-400 mt-0.5">
              {productCount.toLocaleString()} produto{productCount !== 1 ? 's' : ''}
              {platform && <span className="ml-1.5 text-neutral-300">/ {platform}</span>}
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[11px] text-neutral-400 font-medium">INCI</span>
          <span className={cn('text-sm font-semibold tabular-nums', getInciTextColor(inciRate))}>
            {inciPercent}%
          </span>
        </div>
        <div className="h-1 w-full rounded-full bg-neutral-100 overflow-hidden">
          <div
            className={cn('h-full rounded-full transition-all duration-500', getInciBarColor(inciRate))}
            style={{ width: `${inciPercent}%` }}
          />
        </div>
      </div>
    </Link>
  );
}
