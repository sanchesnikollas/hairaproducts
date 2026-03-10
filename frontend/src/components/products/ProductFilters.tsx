import { Search } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { InputGroup, InputGroupAddon, InputGroupInput, InputGroupText } from '@/components/ui/input-group';
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
  statusCounts,
}: ProductFiltersProps) {
  return (
    <div className="space-y-4">
      {/* Status Tabs */}
      <Tabs value={status} onValueChange={(val) => onStatusChange(val as StatusFilter)}>
        <TabsList variant="line" className="gap-0">
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value} className="gap-2 px-3">
              {tab.label}
              <Badge
                variant="secondary"
                className="h-5 min-w-[1.25rem] px-1.5 text-[10px] tabular-nums"
              >
                {statusCounts[tab.value]}
              </Badge>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Search + Category + Toggles */}
      <div className="flex flex-wrap items-center gap-3">
        <InputGroup className="min-w-[240px] max-w-sm flex-1">
          <InputGroupAddon align="inline-start">
            <InputGroupText>
              <Search className="size-4 text-ink-faint" />
            </InputGroupText>
          </InputGroupAddon>
          <InputGroupInput
            placeholder="Search products..."
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
          />
        </InputGroup>

        <Select value={category || '__all__'} onValueChange={(v) => onCategoryChange(v === '__all__' ? '' : (v ?? ''))}>
          <SelectTrigger className="min-w-[160px]">
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
        >
          Exclude Kits
        </Button>

        <Button
          variant={verifiedOnly ? 'default' : 'outline'}
          size="sm"
          onClick={() => onVerifiedOnlyChange(!verifiedOnly)}
        >
          Verified INCI Only
        </Button>
      </div>
    </div>
  );
}
