import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import SealBadge from '@/components/SealBadge';
import type { Product } from '@/types/api';

interface ProductCardProps {
  product: Product;
  brandSlug: string;
  onClick?: () => void;
}

function getStatusDot(status: string): string | null {
  switch (status) {
    case 'verified_inci': return 'bg-emerald-500';
    case 'catalog_only': return 'bg-amber-400';
    case 'quarantined': return 'bg-red-500';
    default: return null;
  }
}

function PlaceholderImage() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-neutral-50">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-8 h-8 text-neutral-300"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"
        />
      </svg>
    </div>
  );
}

export default function ProductCard({ product, brandSlug, onClick }: ProductCardProps) {
  const allSeals = [
    ...(product.product_labels?.detected ?? []),
    ...(product.product_labels?.inferred ?? []),
  ];
  const visibleSeals = allSeals.slice(0, 3);
  const extraCount = allSeals.length - visibleSeals.length;
  const dotColor = getStatusDot(product.verification_status);

  const cardContent = (
    <div className="bg-white rounded-xl border border-neutral-200/60 overflow-hidden transition-all duration-200 group-hover/product-card:shadow-md group-hover/product-card:border-neutral-300/60">
      <div className="aspect-square w-full overflow-hidden bg-neutral-50">
        {product.image_url_main ? (
          <img
            src={product.image_url_main}
            alt={product.product_name}
            className="w-full h-full object-contain transition-transform duration-300 group-hover/product-card:scale-105"
            loading="lazy"
          />
        ) : (
          <PlaceholderImage />
        )}
      </div>
      <div className="px-3.5 py-3 space-y-2">
        <div className="flex items-start gap-2">
          {dotColor && (
            <span className={cn('w-1.5 h-1.5 rounded-full mt-1.5 shrink-0', dotColor)} />
          )}
          <p className="text-[13px] font-medium text-neutral-800 line-clamp-2 leading-snug">
            {product.product_name}
          </p>
        </div>
        {visibleSeals.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {visibleSeals.map((seal) => (
              <SealBadge key={seal} seal={seal} />
            ))}
            {extraCount > 0 && (
              <span className="text-[10px] text-neutral-400 self-center">
                +{extraCount}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="block w-full text-left group/product-card">
        {cardContent}
      </button>
    );
  }

  return (
    <Link to={`/brands/${brandSlug}/products/${product.id}`} className="block group/product-card">
      {cardContent}
    </Link>
  );
}
