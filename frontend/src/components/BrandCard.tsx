import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface BrandCardProps {
  slug: string;
  name: string;
  productCount: number;
  inciRate: number;
  platform: string | null;
}

function getInciBarColor(rate: number): string {
  if (rate >= 0.9) return 'bg-emerald-500';
  if (rate >= 0.5) return 'bg-amber-500';
  return 'bg-red-500';
}

const AVATAR_COLORS = [
  'bg-violet-500',
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-pink-500',
  'bg-indigo-500',
  'bg-teal-500',
  'bg-orange-500',
];

function getAvatarColor(slug: string): string {
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) & 0xffffffff;
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
}

export default function BrandCard({ slug, name, productCount, inciRate, platform }: BrandCardProps) {
  const inciPercent = Math.round(inciRate * 100);
  const avatarColor = getAvatarColor(slug);

  return (
    <Link to={`/brands/${slug}`} className="block group/brand-card">
      <Card
        className={cn(
          'transition-shadow duration-200 cursor-pointer',
          'group-hover/brand-card:shadow-md'
        )}
      >
        <CardContent className="flex flex-col gap-3 pt-2">
          {/* Header row: avatar + name + platform badge */}
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-base',
                avatarColor
              )}
            >
              {name.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-card-foreground truncate">{name}</p>
              {platform && (
                <Badge variant="outline" className="mt-0.5 text-[10px] px-1.5 py-0 h-auto">
                  {platform}
                </Badge>
              )}
            </div>
          </div>

          {/* Product count */}
          <p className="text-xs text-muted-foreground">
            {productCount.toLocaleString()} product{productCount !== 1 ? 's' : ''}
          </p>

          {/* INCI rate bar */}
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">INCI Coverage</span>
              <span className="font-medium text-card-foreground">{inciPercent}%</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
              <div
                className={cn('h-full rounded-full transition-all duration-300', getInciBarColor(inciRate))}
                style={{ width: `${inciPercent}%` }}
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
