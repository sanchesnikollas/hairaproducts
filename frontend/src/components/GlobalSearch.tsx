import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
} from '@/components/ui/command';
import { getProducts } from '@/lib/api';
import type { Product } from '@/types/api';

interface GlobalSearchProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export default function GlobalSearch({ open, onOpenChange }: GlobalSearchProps) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Product[]>([]);
  const [loading, setLoading] = useState(false);

  const search = useCallback(async (searchQuery: string) => {
    if (!searchQuery || searchQuery.length < 2) {
      setResults([]);
      return;
    }
    setLoading(true);
    try {
      const data = await getProducts({ search: searchQuery, per_page: 10 });
      setResults(data.items);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      search(query);
    }, 300);
    return () => clearTimeout(timer);
  }, [query, search]);

  useEffect(() => {
    if (!open) {
      setQuery('');
      setResults([]);
    }
  }, [open]);

  const handleSelect = (productId: string) => {
    onOpenChange(false);
    navigate(`/products?highlight=${productId}`);
  };

  return (
    <CommandDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Search Products"
      description="Search for products by name across all brands"
    >
      <CommandInput
        placeholder="Search products..."
        value={query}
        onValueChange={setQuery}
      />
      <CommandList>
        {loading && (
          <div className="py-6 text-center text-sm text-ink-muted">
            Searching...
          </div>
        )}
        {!loading && query.length >= 2 && results.length === 0 && (
          <CommandEmpty>No products found.</CommandEmpty>
        )}
        {!loading && results.length > 0 && (
          <CommandGroup heading="Products">
            {results.map((product) => (
              <CommandItem
                key={product.id}
                value={product.product_name}
                onSelect={() => handleSelect(product.id)}
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm font-medium text-ink">
                    {product.product_name}
                  </span>
                  <span className="text-xs text-ink-muted">
                    {product.brand_slug}
                    {product.product_category ? ` · ${product.product_category}` : ''}
                  </span>
                </div>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {!loading && query.length < 2 && (
          <div className="py-6 text-center text-sm text-ink-muted">
            Type at least 2 characters to search...
          </div>
        )}
      </CommandList>
    </CommandDialog>
  );
}
