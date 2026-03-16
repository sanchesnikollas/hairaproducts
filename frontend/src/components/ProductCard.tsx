import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import SealBadge from '@/components/SealBadge';
import type { Product } from '@/types/api';

interface ProductCardProps {
  product: Product;
  brandSlug: string;
}

function PlaceholderImage() {
  return (
    <div className="w-full h-full flex items-center justify-center bg-muted">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-10 h-10 text-muted-foreground/40"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 7h18M3 7a2 2 0 00-2 2v9a2 2 0 002 2h18a2 2 0 002-2V9a2 2 0 00-2-2M3 7V5a2 2 0 012-2h3m9 0h3a2 2 0 012 2v2M9 3h6"
        />
      </svg>
    </div>
  );
}

export default function ProductCard({ product, brandSlug }: ProductCardProps) {
  const allSeals = [
    ...(product.product_labels?.detected ?? []),
    ...(product.product_labels?.inferred ?? []),
  ];
  const visibleSeals = allSeals.slice(0, 3);
  const extraCount = allSeals.length - visibleSeals.length;

  return (
    <Link to={`/brands/${brandSlug}/products/${product.id}`} className="block group/product-card">
      <Card className="overflow-hidden transition-shadow duration-200 group-hover/product-card:shadow-md">
        {/* Image area */}
        <div className="aspect-square w-full overflow-hidden bg-muted">
          {product.image_url_main ? (
            <img
              src={product.image_url_main}
              alt={product.product_name}
              className={cn(
                'w-full h-full object-contain transition-transform duration-300',
                'group-hover/product-card:scale-105'
              )}
              loading="lazy"
            />
          ) : (
            <PlaceholderImage />
          )}
        </div>

        <CardContent className="flex flex-col gap-2 py-3">
          {/* Product name */}
          <p className="text-sm font-medium text-card-foreground line-clamp-2 leading-snug">
            {product.product_name}
          </p>

          {/* Seal badges */}
          {visibleSeals.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {visibleSeals.map((seal) => (
                <SealBadge key={seal} seal={seal} />
              ))}
              {extraCount > 0 && (
                <span className="text-[11px] text-muted-foreground self-center">
                  +{extraCount}
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
