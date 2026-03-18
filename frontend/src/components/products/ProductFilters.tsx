import { Search, Filter } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

export type StatusFilter = 'all' | 'verified_inci' | 'catalog_only' | 'quarantined';

interface ProductFiltersProps {
  status: StatusFilter;
  onStatusChange: (status: StatusFilter) => void;
  search: string;
  onSearchChange: (search: string) => void;
  category: string;
  onCategoryChange: (category: string) => void;
  excludeKits: boolean;
  onExcludeKitsChange: (exclude: boolean) => void;
  verifiedOnly: boolean;
  onVerifiedOnlyChange: (verified: boolean) => void;
  categories: string[];
  statusCounts: {
    all: number;
    verified_inci: number;
    catalog_only: number;
    quarantined: number;
  };
}

const STATUS_TABS: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'verified_inci', label: 'Verified' },
  { value: 'catalog_only', label: 'Catalog Only' },
  { value: 'quarantined', label: 'Quarantined' },
];

export default function ProductFilters({
  status,
  onStatusChange,
  search,
  onSearchChange,
  category,
  onCategoryChange,
  excludeKits,
  onExcludeKitsChange,
  verifiedOnly,
  onVerifiedOnlyChange,
  categories,
}: ProductFiltersProps) {
  return (
    <div className="space-y-3">
      {/* Search + Filters Row */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-ink-faint pointer-events-none" />
          <Input
            placeholder="Search products..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="pl-9"
          />
        </div>

        <Select value={category || '__all__'} onValueChange={(v) => onCategoryChange(v === '__all__' ? '' : (v ?? ''))}>
          <SelectTrigger className="min-w-[160px] w-auto">
            <Filter className="size-3.5 text-ink-faint mr-1.5" />
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">All categories</SelectItem>
            {categories.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant={excludeKits ? 'default' : 'outline'}
          size="sm"
          onClick={() => onExcludeKitsChange(!excludeKits)}
          className="shrink-0"
        >
          Exclude Kits
        </Button>

        <Button
          variant={verifiedOnly ? 'default' : 'outline'}
          size="sm"
          onClick={() => onVerifiedOnlyChange(!verifiedOnly)}
          className="shrink-0"
        >
          Verified Only
        </Button>
      </div>

      {/* Status Tabs */}
      <Tabs value={status} onValueChange={(val) => onStatusChange(val as StatusFilter)}>
        <TabsList variant="line" className="gap-0">
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="px-4">
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
