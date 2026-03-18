# Quick Polish Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform HAIRA frontend from a browsing tool into a fast validation dashboard for project owners.

**Architecture:** Replace Home hero + stats with a computed health score + attention alerts. Add Quarentena and Cobertura tabs to BrandPage. Simplify nav from 6 items to 3. Enhance ProductSheet with collapsible sections and quarantine actions. All changes are frontend-only using existing API endpoints.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 4, Shadcn UI, Motion (motion/react), Sonner (toasts), existing API client (`src/lib/api.ts`)

---

## File Structure

**New files:**
| File | Responsibility |
|------|---------------|
| `frontend/src/components/HealthScore.tsx` | Large health score with semaphore color, computed from brands data |
| `frontend/src/components/AttentionAlerts.tsx` | Clickable alert badges for quarantine + low-INCI brands |
| `frontend/src/components/QuarantineTab.tsx` | Inline quarantine review for a single brand with approve/reject |
| `frontend/src/components/CoverageTab.tsx` | Compact coverage funnel visualization |
| `frontend/src/components/SessionProgress.tsx` | Thin progress bar for quarantine review sessions |

**Modified files:**
| File | Changes |
|------|---------|
| `frontend/src/pages/Home.tsx` | Remove hero + stats grid, add HealthScore + AttentionAlerts, sort brands by attention needed |
| `frontend/src/pages/BrandPage.tsx` | Compact header, add Tabs (Produtos/Quarentena/Cobertura), remove redundant stats row |
| `frontend/src/components/products/ProductSheet.tsx` | Add status indicators on section headers, default collapsed, add quarantine footer actions |
| `frontend/src/components/Layout.tsx` | Remove admin nav items + separator + quarantine polling, add Explorador link |
| `frontend/src/App.tsx` | Remove admin routes, add /explorer + redirects |
| `frontend/src/lib/api.ts` | Add `getQuarantineByBrand(slug)` helper |
| `frontend/src/components/BrandCard.tsx` | Add quarantine dot indicator, semaphore INCI bar already exists |
| `frontend/src/components/SealBadge.tsx` | Add `variant` prop for inferred (dashed border) vs detected (solid) |
| `frontend/src/components/ProductCard.tsx` | Add left border color by verification status |

---

## Chunk 1: Foundation — API + Shared Components

### Task 1: Add quarantine-by-brand API helper

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add `getQuarantineByBrand` function**

Add after the existing `getQuarantine` function at line ~109:

```typescript
export async function getQuarantineByBrand(brandSlug: string, reviewStatus = 'pending'): Promise<QuarantineItem[]> {
  return fetchJSON<QuarantineItem[]>(`/quarantine?brand=${brandSlug}&review_status=${reviewStatus}`);
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add getQuarantineByBrand API helper"
```

### Task 2: Create HealthScore component

**Files:**
- Create: `frontend/src/components/HealthScore.tsx`

- [ ] **Step 1: Create HealthScore component**

```tsx
import { motion } from 'motion/react';

interface HealthScoreProps {
  score: number;
  totalProducts: number;
  totalBrands: number;
}

function getScoreColor(score: number): { text: string; bg: string } {
  if (score >= 80) return { text: 'text-emerald-600', bg: 'bg-emerald-50' };
  if (score >= 50) return { text: 'text-amber-600', bg: 'bg-amber-50' };
  return { text: 'text-red-600', bg: 'bg-red-50' };
}

export default function HealthScore({ score, totalProducts, totalBrands }: HealthScoreProps) {
  const { text, bg } = getScoreColor(score);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className={`rounded-2xl ${bg} p-8 text-center`}
    >
      <p className={`font-display text-7xl font-bold tabular-nums ${text}`}>
        {Math.round(score)}%
      </p>
      <p className="mt-2 text-sm text-ink-muted">
        {totalProducts.toLocaleString()} produtos, {totalBrands} marcas, {Math.round(score)}% INCI medio
      </p>
    </motion.div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/HealthScore.tsx
git commit -m "feat: add HealthScore component with semaphore colors"
```

### Task 3: Create AttentionAlerts component

**Files:**
- Create: `frontend/src/components/AttentionAlerts.tsx`

- [ ] **Step 1: Create AttentionAlerts component**

```tsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Badge } from '@/components/ui/badge';
import { getQuarantine } from '@/lib/api';
import type { QuarantineItem } from '@/types/api';

interface BrandData {
  brand_slug: string;
  brand_name: string;
  product_count: number;
  inci_rate: number;
  quarantine_count?: number;
  missing_inci?: number;
}

interface AttentionAlertsProps {
  brands: BrandData[];
}

export default function AttentionAlerts({ brands }: AttentionAlertsProps) {
  const [quarantineItems, setQuarantineItems] = useState<QuarantineItem[]>([]);

  useEffect(() => {
    getQuarantine('pending')
      .then(setQuarantineItems)
      .catch(() => {});
  }, []);

  const totalQuarantine = quarantineItems.length;

  // Brands with <50% INCI
  const lowInciBrands = brands.filter((b) => b.inci_rate < 0.5);

  // Per-brand quarantine counts
  const quarantineByBrand: Record<string, number> = {};
  for (const item of quarantineItems) {
    const slug = item.brand_slug ?? 'unknown';
    quarantineByBrand[slug] = (quarantineByBrand[slug] || 0) + 1;
  }

  // Per-brand missing INCI counts
  const brandsWithGaps = brands
    .map((b) => ({
      ...b,
      missing_inci: Math.round(b.product_count * (1 - b.inci_rate)),
    }))
    .filter((b) => b.missing_inci > 5)
    .sort((a, b) => b.missing_inci - a.missing_inci)
    .slice(0, 3);

  const hasAlerts = totalQuarantine > 0 || lowInciBrands.length > 0 || brandsWithGaps.length > 0;

  if (!hasAlerts) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-emerald-50 text-emerald-700 text-sm"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Base saudavel — nenhum alerta
      </motion.div>
    );
  }

  // Find first brand with quarantine items for the link
  const firstQuarantineBrand = Object.keys(quarantineByBrand)[0];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.4 }}
      className="flex flex-wrap gap-2"
    >
      {totalQuarantine > 0 && firstQuarantineBrand && (
        <Link to={`/brands/${firstQuarantineBrand}?tab=quarentena`}>
          <Badge variant="destructive" className="cursor-pointer text-xs px-3 py-1.5 hover:opacity-90">
            {totalQuarantine} em quarentena
          </Badge>
        </Link>
      )}

      {lowInciBrands.length > 0 && (
        <Link to="/brands">
          <Badge className="cursor-pointer text-xs px-3 py-1.5 bg-amber-100 text-amber-800 border-amber-200 hover:bg-amber-200">
            {lowInciBrands.length} marcas &lt;50% INCI
          </Badge>
        </Link>
      )}

      {brandsWithGaps.map((b) => (
        <Link key={b.brand_slug} to={`/brands/${b.brand_slug}`}>
          <Badge variant="outline" className="cursor-pointer text-xs px-3 py-1.5 hover:bg-ink/5">
            {b.brand_name}: {b.missing_inci} sem INCI
          </Badge>
        </Link>
      ))}
    </motion.div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AttentionAlerts.tsx
git commit -m "feat: add AttentionAlerts component with quarantine and INCI alerts"
```

### Task 4: Create SessionProgress component

**Files:**
- Create: `frontend/src/components/SessionProgress.tsx`

- [ ] **Step 1: Create SessionProgress component**

```tsx
import { motion } from 'motion/react';

interface SessionProgressProps {
  reviewed: number;
  total: number;
}

export default function SessionProgress({ reviewed, total }: SessionProgressProps) {
  if (total === 0) return null;

  const allDone = reviewed >= total;
  const percent = Math.round((reviewed / total) * 100);

  if (allDone) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="text-center py-2 text-sm text-emerald-600"
      >
        <svg className="inline-block mr-1.5 -mt-0.5" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        Tudo revisado
      </motion.div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-ink-muted">
        <span>{reviewed}/{total} revisados</span>
        <span>{percent}%</span>
      </div>
      <div className="h-1 w-full rounded-full bg-ink/5 overflow-hidden">
        <motion.div
          className="h-full rounded-full bg-champagne"
          initial={{ width: 0 }}
          animate={{ width: `${percent}%` }}
          transition={{ duration: 0.4 }}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SessionProgress.tsx
git commit -m "feat: add SessionProgress component for quarantine review tracking"
```

### Task 5: Create QuarantineTab component

**Files:**
- Create: `frontend/src/components/QuarantineTab.tsx`

- [ ] **Step 1: Create QuarantineTab component**

This is the inline quarantine review that lives inside the brand page. Adapts the existing `QuarantineReview.tsx` patterns but simplified for single-brand use.

```tsx
import { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAPI } from '@/hooks/useAPI';
import { getQuarantineByBrand, approveQuarantine, rejectQuarantine } from '@/lib/api';
import type { QuarantineItem } from '@/types/api';
import SessionProgress from '@/components/SessionProgress';

interface QuarantineTabProps {
  brandSlug: string;
  onCountChange?: (count: number) => void;
}

export default function QuarantineTab({ brandSlug, onCountChange }: QuarantineTabProps) {
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());
  const [confirmingReject, setConfirmingReject] = useState<string | null>(null);

  const fetcher = useCallback(() => getQuarantineByBrand(brandSlug), [brandSlug]);
  const { data: items, loading, error, refetch } = useAPI(fetcher, [brandSlug]);

  const visibleItems = useMemo(
    () => items?.filter((item) => !removedIds.has(item.id)) ?? [],
    [items, removedIds]
  );

  const totalItems = items?.length ?? 0;
  const reviewedCount = removedIds.size;

  async function handleApprove(item: QuarantineItem) {
    try {
      await approveQuarantine(item.id);
      setRemovedIds((prev) => new Set(prev).add(item.id));
      onCountChange?.(totalItems - removedIds.size - 1);
      toast.success(`${item.product_name ?? 'Produto'} aprovado — ${visibleItems.length - 1} restantes em quarentena`);
    } catch {
      toast.error('Falha ao aprovar produto');
    }
  }

  async function handleReject(item: QuarantineItem) {
    if (confirmingReject !== item.id) {
      setConfirmingReject(item.id);
      return;
    }
    try {
      await rejectQuarantine(item.id);
      setRemovedIds((prev) => new Set(prev).add(item.id));
      setConfirmingReject(null);
      onCountChange?.(totalItems - removedIds.size - 1);
      toast.success(`${item.product_name ?? 'Produto'} rejeitado`);
    } catch {
      toast.error('Falha ao rejeitar produto');
    }
  }

  if (loading) {
    return (
      <div className="space-y-3 py-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-ink/5 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-coral mb-3">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Tentar novamente</Button>
      </div>
    );
  }

  if (totalItems === 0) {
    return (
      <div className="text-center py-12">
        <svg className="mx-auto mb-3 text-emerald-500" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        <p className="text-sm text-ink-muted">Nenhum produto em quarentena</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 py-2">
      <SessionProgress reviewed={reviewedCount} total={totalItems} />

      <AnimatePresence mode="popLayout">
        {visibleItems.map((item) => {
          const rejectionCodes = item.rejection_code
            ? item.rejection_code.split(',').map((s) => s.trim())
            : [];

          return (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 40, transition: { duration: 0.25 } }}
              className="flex items-center gap-3 p-3 rounded-lg border border-ink/5 bg-white"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {item.product_name ?? 'Produto desconhecido'}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="destructive" className="text-[10px] h-4 px-1.5">
                    {item.rejection_reason}
                  </Badge>
                  {rejectionCodes.map((code) => (
                    <Badge key={code} variant="outline" className="text-[10px] h-4 px-1.5 text-coral border-coral/30">
                      {code}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 text-xs"
                  onClick={() => handleApprove(item)}
                >
                  Aprovar
                </Button>
                <Button
                  size="sm"
                  variant={confirmingReject === item.id ? 'destructive' : 'outline'}
                  className="h-7 text-xs"
                  onClick={() => handleReject(item)}
                  onBlur={() => setConfirmingReject(null)}
                >
                  {confirmingReject === item.id ? 'Confirmar' : 'Rejeitar'}
                </Button>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/QuarantineTab.tsx
git commit -m "feat: add QuarantineTab for inline brand quarantine review"
```

### Task 6: Create CoverageTab component

**Files:**
- Create: `frontend/src/components/CoverageTab.tsx`

- [ ] **Step 1: Create CoverageTab component**

```tsx
import { motion } from 'motion/react';
import type { BrandCoverage } from '@/types/api';

interface CoverageTabProps {
  coverage: BrandCoverage;
}

interface FunnelStep {
  label: string;
  count: number;
  color: string;
}

export default function CoverageTab({ coverage }: CoverageTabProps) {
  const steps: FunnelStep[] = [
    { label: 'Descobertos', count: coverage.discovered_total, color: 'bg-ink/20' },
    { label: 'Hair Products', count: coverage.hair_total, color: 'bg-blue-400' },
    { label: 'Extraidos', count: coverage.extracted_total, color: 'bg-amber-400' },
    { label: 'INCI Verificado', count: coverage.verified_inci_total, color: 'bg-emerald-500' },
  ];

  const maxCount = Math.max(...steps.map((s) => s.count), 1);

  return (
    <div className="py-4 space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-ink-faint font-semibold">
        Funil de Cobertura
      </h3>
      <div className="space-y-2">
        {steps.map((step, i) => {
          const widthPercent = Math.max((step.count / maxCount) * 100, 4);
          return (
            <motion.div
              key={step.label}
              initial={{ opacity: 0, x: -12 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.08, duration: 0.3 }}
              className="flex items-center gap-3"
            >
              <span className="text-xs text-ink-muted w-28 shrink-0 text-right">
                {step.label}
              </span>
              <div className="flex-1 h-6 rounded bg-ink/[0.03] overflow-hidden">
                <motion.div
                  className={`h-full rounded ${step.color} flex items-center px-2`}
                  initial={{ width: 0 }}
                  animate={{ width: `${widthPercent}%` }}
                  transition={{ delay: i * 0.08 + 0.15, duration: 0.5, ease: 'easeOut' }}
                >
                  <span className="text-xs font-medium text-white drop-shadow-sm">
                    {step.count.toLocaleString()}
                  </span>
                </motion.div>
              </div>
            </motion.div>
          );
        })}
      </div>

      {/* Summary stats */}
      <div className="flex items-center gap-4 pt-2 text-xs text-ink-muted border-t border-ink/5 mt-4">
        <span>Catalog Only: {coverage.catalog_only_total}</span>
        <span>Quarentena: {coverage.quarantined_total}</span>
        <span>Kits: {coverage.kits_total}</span>
        <span>Non-Hair: {coverage.non_hair_total}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CoverageTab.tsx
git commit -m "feat: add CoverageTab with animated coverage funnel"
```

---

## Chunk 2: Enhance Existing Components

### Task 7: Add quarantine dot and semaphore colors to BrandCard

**Files:**
- Modify: `frontend/src/components/BrandCard.tsx`

- [ ] **Step 1: Add `quarantineCount` prop and red dot indicator**

Update BrandCardProps to accept `quarantineCount`:

```typescript
interface BrandCardProps {
  slug: string;
  name: string;
  productCount: number;
  inciRate: number;
  platform: string | null;
  quarantineCount?: number;
}
```

Update the component signature:

```typescript
export default function BrandCard({ slug, name, productCount, inciRate, platform, quarantineCount = 0 }: BrandCardProps) {
```

Add red dot after the avatar div (inside the header row flex container), right after the avatar `<div>`:

```tsx
{quarantineCount > 0 && (
  <span className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-white" />
)}
```

And wrap the avatar in `relative`:

Change the avatar div to include `relative`:
```tsx
<div className={cn('relative flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-white font-semibold text-base', avatarColor)}>
```

The `getInciBarColor` function already implements semaphore colors (emerald/amber/red) so no changes needed there.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BrandCard.tsx
git commit -m "feat: add quarantine dot indicator to BrandCard"
```

### Task 8: Add left border status color to ProductCard

**Files:**
- Modify: `frontend/src/components/ProductCard.tsx`

- [ ] **Step 1: Add status border color**

Add a helper function before the component:

```typescript
function getStatusBorderClass(status: string): string {
  switch (status) {
    case 'verified_inci': return 'border-l-4 border-l-emerald-500';
    case 'catalog_only': return 'border-l-4 border-l-amber-400';
    case 'quarantined': return 'border-l-4 border-l-red-500';
    default: return '';
  }
}
```

Update the Card component to include the border class:

```tsx
<Card className={cn('overflow-hidden transition-shadow duration-200 group-hover/product-card:shadow-md', getStatusBorderClass(product.verification_status))}>
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProductCard.tsx
git commit -m "feat: add verification status border color to ProductCard"
```

### Task 9: Add inferred variant to SealBadge

**Files:**
- Modify: `frontend/src/components/SealBadge.tsx`

- [ ] **Step 1: Add `variant` prop**

Update the interface:

```typescript
interface SealBadgeProps {
  seal: string;
  variant?: 'detected' | 'inferred';
  className?: string;
}
```

Update the component:

```typescript
export default function SealBadge({ seal, variant = 'detected', className }: SealBadgeProps) {
  const isInferred = variant === 'inferred';
  return (
    <Badge
      variant="outline"
      className={cn(
        'text-[11px] h-auto px-2 py-0.5 font-medium tracking-wide',
        getSealClassName(seal),
        isInferred && 'border-dashed opacity-75',
        className
      )}
    >
      {getSealLabel(seal)}
    </Badge>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SealBadge.tsx
git commit -m "feat: add inferred variant with dashed border to SealBadge"
```

---

## Chunk 3: Home Page — Health Dashboard

### Task 10: Replace Home page with Health Dashboard

**Files:**
- Modify: `frontend/src/pages/Home.tsx`

- [ ] **Step 1: Rewrite Home.tsx**

Replace the entire Home component. Key changes:
- Remove hero text and decorative stats bar
- Add HealthScore computed from brands data
- Add AttentionAlerts
- Sort brand grid by attention needed (lowest INCI rate first)

```tsx
import { useMemo } from 'react';
import { motion } from 'motion/react';
import BrandCard from '@/components/BrandCard';
import HealthScore from '@/components/HealthScore';
import AttentionAlerts from '@/components/AttentionAlerts';
import LoadingState, { ErrorState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getBrands, getQuarantine } from '@/lib/api';
import type { BrandCoverage, BrandSummary, QuarantineItem } from '@/types/api';

type BrandItem = BrandCoverage | BrandSummary;

function isBrandSummary(b: BrandItem): b is BrandSummary {
  return 'brand_name' in b;
}

function getBrandName(b: BrandItem): string {
  if (isBrandSummary(b)) return b.brand_name;
  return b.brand_slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function getBrandProductCount(b: BrandItem): number {
  if (isBrandSummary(b)) return b.product_count;
  return (b as BrandCoverage).extracted_total;
}

function getBrandInciRate(b: BrandItem): number {
  if (isBrandSummary(b)) return b.inci_rate;
  return (b as BrandCoverage).verified_inci_rate;
}

function getBrandPlatform(b: BrandItem): string | null {
  if (isBrandSummary(b)) return b.platform;
  return null;
}

export default function Home() {
  const { data: brands, loading: brandsLoading, error: brandsError } = useAPI<BrandCoverage[]>(getBrands);
  const { data: quarantineItems } = useAPI<QuarantineItem[]>(() => getQuarantine('pending'));

  if (brandsLoading) return <LoadingState message="Loading HAIRA..." />;
  if (brandsError) return <ErrorState message={brandsError} />;
  if (!brands) return null;

  // Compute weighted health score: sum(inci_rate * product_count) / sum(product_count)
  const totalProducts = brands.reduce((sum, b) => sum + getBrandProductCount(b), 0);
  const weightedSum = brands.reduce(
    (sum, b) => sum + getBrandInciRate(b) * getBrandProductCount(b),
    0
  );
  const healthScore = totalProducts > 0 ? (weightedSum / totalProducts) * 100 : 0;

  // Quarantine counts per brand
  const quarantineByBrand: Record<string, number> = {};
  for (const item of quarantineItems ?? []) {
    const slug = item.brand_slug ?? 'unknown';
    quarantineByBrand[slug] = (quarantineByBrand[slug] || 0) + 1;
  }

  // Sort brands: lowest INCI rate first, most quarantine items first
  const sortedBrands = [...brands].sort((a, b) => {
    const aQuarantine = quarantineByBrand[a.brand_slug] ?? 0;
    const bQuarantine = quarantineByBrand[b.brand_slug] ?? 0;
    // Primary: brands with quarantine items first
    if (aQuarantine !== bQuarantine) return bQuarantine - aQuarantine;
    // Secondary: lowest INCI rate first
    return getBrandInciRate(a) - getBrandInciRate(b);
  });

  // Prepare brands data for AttentionAlerts
  const alertBrands = brands.map((b) => ({
    brand_slug: b.brand_slug,
    brand_name: getBrandName(b),
    product_count: getBrandProductCount(b),
    inci_rate: getBrandInciRate(b),
  }));

  return (
    <div className="space-y-8">
      {/* Health Score */}
      <HealthScore
        score={healthScore}
        totalProducts={totalProducts}
        totalBrands={brands.length}
      />

      {/* Attention Alerts */}
      <AttentionAlerts brands={alertBrands} />

      {/* Brand Grid */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.3 }}
      >
        <h2 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-4">
          Marcas
        </h2>
        {sortedBrands.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {sortedBrands.map((brand, i) => (
              <motion.div
                key={brand.brand_slug}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.35 + i * 0.04 }}
              >
                <BrandCard
                  slug={brand.brand_slug}
                  name={getBrandName(brand)}
                  productCount={getBrandProductCount(brand)}
                  inciRate={getBrandInciRate(brand)}
                  platform={getBrandPlatform(brand)}
                  quarantineCount={quarantineByBrand[brand.brand_slug] ?? 0}
                />
              </motion.div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-ink-faint">No brands found.</p>
        )}
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "feat: replace Home hero with health dashboard, alerts, and sorted brand grid"
```

---

## Chunk 4: Brand Page — Tabbed Validation

### Task 11: Add tabs to BrandPage

**Files:**
- Modify: `frontend/src/pages/BrandPage.tsx`

- [ ] **Step 1: Rewrite BrandPage.tsx with tabs**

Replace the entire BrandPage. Key changes:
- Compact header with INCI as large semaphore number
- Remove redundant stats grid
- Add Tabs: Produtos (default) | Quarentena | Cobertura
- Produtos tab keeps existing product grid + filters
- Quarentena tab uses QuarantineTab component
- Cobertura tab uses CoverageTab component
- Read `?tab=quarentena` from URL search params

```tsx
import { useState, useMemo, useCallback } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import ProductCard from '@/components/ProductCard';
import SealBadge from '@/components/SealBadge';
import QuarantineTab from '@/components/QuarantineTab';
import CoverageTab from '@/components/CoverageTab';
import LoadingState, { ErrorState, EmptyState } from '@/components/LoadingState';
import { useAPI } from '@/hooks/useAPI';
import { getBrandCoverage, getBrandProducts } from '@/lib/api';
import type { ProductFilters } from '@/lib/api';

function formatBrandName(slug: string): string {
  return slug
    .split(/[-_]/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function getInciColor(rate: number): string {
  if (rate >= 0.8) return 'text-emerald-600';
  if (rate >= 0.5) return 'text-amber-600';
  return 'text-red-600';
}

const PER_PAGE = 24;

export default function BrandPage() {
  const { slug } = useParams<{ slug: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTab = searchParams.get('tab') ?? 'produtos';
  const [activeTab, setActiveTab] = useState(initialTab);
  const [search, setSearch] = useState('');
  const [verifiedOnly, setVerifiedOnly] = useState(false);
  const [category, setCategory] = useState('');
  const [page, setPage] = useState(1);
  const [quarantineCount, setQuarantineCount] = useState<number | null>(null);

  const filters: Omit<ProductFilters, 'brand'> = useMemo(
    () => ({
      search: search || undefined,
      verified_only: verifiedOnly || undefined,
      category: category || undefined,
      page,
      per_page: PER_PAGE,
    }),
    [search, verifiedOnly, category, page]
  );

  const { data: coverage, loading: coverageLoading, error: coverageError } = useAPI(
    () => getBrandCoverage(slug!),
    [slug]
  );

  const { data: productsResponse, loading: productsLoading, error: productsError } = useAPI(
    () => getBrandProducts(slug!, filters),
    [slug, search, verifiedOnly, category, page]
  );

  const products = productsResponse?.items ?? [];
  const total = productsResponse?.total ?? 0;
  const totalPages = Math.ceil(total / PER_PAGE);

  const categories = useMemo(() => {
    const cats = new Set<string>();
    for (const p of products) {
      if (p.product_category) cats.add(p.product_category);
    }
    return Array.from(cats).sort();
  }, [products]);

  const handleSearch = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearch(e.target.value);
    setPage(1);
  }, []);

  function handleTabChange(value: string | number | null) {
    if (value && typeof value === 'string') {
      setActiveTab(value);
      setSearchParams(value === 'produtos' ? {} : { tab: value });
    }
  }

  if (coverageLoading) return <LoadingState message="Loading brand..." />;
  if (coverageError) return <ErrorState message={coverageError} />;
  if (!coverage) return null;

  const inciPercent = Math.round(coverage.verified_inci_rate * 100);
  const displayQuarantineCount = quarantineCount ?? coverage.quarantined_total;

  return (
    <div className="space-y-6">
      {/* Compact Header */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-6"
      >
        <div className="flex-1 min-w-0">
          <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">
            {formatBrandName(slug!)}
          </h1>
          <div className="flex items-center gap-2 mt-1 text-sm text-ink-muted">
            <Badge variant="outline" className="text-xs">{coverage.status}</Badge>
            <span>{coverage.extracted_total} produtos</span>
            <span className="text-ink-faint">·</span>
            <span>{coverage.verified_inci_total} verificados</span>
            {displayQuarantineCount > 0 && (
              <>
                <span className="text-ink-faint">·</span>
                <span className="text-red-500">{displayQuarantineCount} quarentena</span>
              </>
            )}
          </div>
        </div>
        <div className="text-right shrink-0">
          <p className={`font-display text-5xl font-bold tabular-nums ${getInciColor(coverage.verified_inci_rate)}`}>
            {inciPercent}%
          </p>
          <p className="text-xs text-ink-faint uppercase tracking-wider mt-1">INCI</p>
        </div>
      </motion.div>

      {/* Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.1 }}
      >
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="produtos">Produtos</TabsTrigger>
            <TabsTrigger value="quarentena" className="gap-1.5">
              Quarentena
              {displayQuarantineCount > 0 && (
                <Badge variant="destructive" className="text-[10px] h-4 px-1.5 ml-1">
                  {displayQuarantineCount}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="cobertura">Cobertura</TabsTrigger>
          </TabsList>

          {/* Produtos Tab */}
          <TabsContent value="produtos">
            {/* Filters */}
            <div className="flex flex-col sm:flex-row gap-3 mt-4">
              <div className="relative flex-1">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"
                  width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                  strokeLinecap="round" strokeLinejoin="round"
                >
                  <circle cx="11" cy="11" r="8" />
                  <path d="M21 21l-4.35-4.35" />
                </svg>
                <input
                  type="text"
                  placeholder="Buscar produtos..."
                  value={search}
                  onChange={handleSearch}
                  className="w-full rounded-lg border border-ink/10 bg-white pl-10 pr-4 py-2 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-champagne/40 focus:border-champagne"
                />
              </div>
              <button
                onClick={() => { setVerifiedOnly(!verifiedOnly); setPage(1); }}
                className={`px-4 py-2 rounded-lg border text-sm transition-colors ${
                  verifiedOnly
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-white border-ink/10 text-ink-muted hover:text-ink'
                }`}
              >
                Apenas verificados
              </button>
              {categories.length > 0 && (
                <select
                  value={category}
                  onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                  className="rounded-lg border border-ink/10 bg-white px-4 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-champagne/40"
                >
                  <option value="">Todas categorias</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Product Grid */}
            {productsLoading ? (
              <LoadingState message="Carregando produtos..." />
            ) : productsError ? (
              <ErrorState message={productsError} />
            ) : products.length === 0 ? (
              <EmptyState title="Nenhum produto encontrado" description="Tente ajustar os filtros." />
            ) : (
              <div className="mt-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {products.map((product, i) => (
                    <motion.div
                      key={product.id}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: 0.02 * i }}
                    >
                      <ProductCard product={product} brandSlug={slug!} />
                    </motion.div>
                  ))}
                </div>

                {totalPages > 1 && (
                  <div className="flex items-center justify-center gap-2 mt-8">
                    <button
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                      className="px-3 py-1.5 rounded-lg border border-ink/10 text-sm text-ink-muted hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Anterior
                    </button>
                    <span className="text-sm text-ink-muted">
                      Pagina {page} de {totalPages}
                    </span>
                    <button
                      disabled={page >= totalPages}
                      onClick={() => setPage(page + 1)}
                      className="px-3 py-1.5 rounded-lg border border-ink/10 text-sm text-ink-muted hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Proxima
                    </button>
                  </div>
                )}
              </div>
            )}
          </TabsContent>

          {/* Quarentena Tab */}
          <TabsContent value="quarentena">
            <QuarantineTab
              brandSlug={slug!}
              onCountChange={(count) => setQuarantineCount(count)}
            />
          </TabsContent>

          {/* Cobertura Tab */}
          <TabsContent value="cobertura">
            <CoverageTab coverage={coverage} />
          </TabsContent>
        </Tabs>
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/BrandPage.tsx
git commit -m "feat: add tabbed brand page with Produtos, Quarentena, and Cobertura"
```

---

## Chunk 5: ProductSheet Enhancement

### Task 12: Enhance ProductSheet with status indicators and quarantine actions

**Files:**
- Modify: `frontend/src/components/products/ProductSheet.tsx`

- [ ] **Step 1: Update default collapsed state and add status icons**

Change the default expanded state (line ~100-107) so all sections start collapsed:

```typescript
const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
  info: false,
  inci: false,
  labels: false,
  quality: false,
  evidence: false,
  edit: false,
});
```

- [ ] **Step 2: Add status indicator to CollapsibleSection**

Update the `CollapsibleSection` component to accept a `status` prop and display it:

```typescript
function CollapsibleSection({
  title,
  icon,
  expanded,
  onToggle,
  badge,
  status,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  badge?: string;
  status?: 'ok' | 'warning' | 'missing';
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-ink/5 last:border-0">
      <button
        className="flex items-center gap-2 w-full py-3 text-left hover:bg-cream/30 transition-colors -mx-2 px-2 rounded"
        onClick={onToggle}
      >
        <span className="text-ink-faint">{icon}</span>
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-faint flex-1">
          {title}
        </span>
        {status === 'ok' && (
          <svg className="text-emerald-500 shrink-0" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        )}
        {status === 'warning' && (
          <svg className="text-amber-500 shrink-0" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 9v4" /><path d="M12 17h.01" />
            <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
          </svg>
        )}
        {badge && (
          <Badge variant="outline" className="text-[10px] h-auto py-0 px-1.5 text-ink-faint">
            {badge}
          </Badge>
        )}
        {expanded ? (
          <ChevronUp className="size-3.5 text-ink-faint" />
        ) : (
          <ChevronDown className="size-3.5 text-ink-faint" />
        )}
      </button>
      {expanded && <div className="pb-4 pt-1">{children}</div>}
    </div>
  );
}
```

- [ ] **Step 3: Add status props to each section usage**

Update the INCI section to pass status:

```tsx
<CollapsibleSection
  title={`INCI Ingredients (${product.inci_ingredients?.length ?? 0})`}
  icon={<FlaskConical className="size-3.5" />}
  expanded={expandedSections.inci}
  onToggle={() => toggleSection('inci')}
  status={product.inci_ingredients && product.inci_ingredients.length > 0 ? 'ok' : 'warning'}
>
```

Update the Basic Info section:

```tsx
<CollapsibleSection
  title="Basic Info"
  icon={<Package className="size-3.5" />}
  expanded={expandedSections.info}
  onToggle={() => toggleSection('info')}
  status={product.description ? 'ok' : 'warning'}
>
```

Update the Labels section:

```tsx
<CollapsibleSection
  title="Labels & Seals"
  icon={<Shield className="size-3.5" />}
  expanded={expandedSections.labels}
  onToggle={() => toggleSection('labels')}
  status={(product.product_labels?.detected?.length || product.product_labels?.inferred?.length) ? 'ok' : 'warning'}
>
```

- [ ] **Step 4: Add quarantine footer actions**

After the edit section's closing `</div>` (the `px-6 pt-5 space-y-1` div), add:

```tsx
{/* Quarantine Footer Actions */}
{product.verification_status === 'quarantined' && (
  <QuarantineActions productId={product.id} productName={product.product_name} onAction={onProductUpdated} />
)}
```

Add a new sub-component at the bottom of the file:

```tsx
function QuarantineActions({
  productId,
  productName,
  onAction,
}: {
  productId: string;
  productName: string;
  onAction: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [confirmingReject, setConfirmingReject] = useState(false);

  async function handleApprove() {
    setBusy(true);
    try {
      // Need to find quarantine record — use the quarantine list endpoint
      const items = await import('@/lib/api').then(m => m.getQuarantine('pending'));
      const match = items.find(q => q.product_id === productId);
      if (match) {
        await import('@/lib/api').then(m => m.approveQuarantine(match.id));
        toast.success(`${productName} aprovado`);
        onAction();
      } else {
        toast.error('Registro de quarentena nao encontrado');
      }
    } catch {
      toast.error('Falha ao aprovar');
    } finally {
      setBusy(false);
    }
  }

  async function handleReject() {
    if (!confirmingReject) {
      setConfirmingReject(true);
      return;
    }
    setBusy(true);
    try {
      const items = await import('@/lib/api').then(m => m.getQuarantine('pending'));
      const match = items.find(q => q.product_id === productId);
      if (match) {
        await import('@/lib/api').then(m => m.rejectQuarantine(match.id));
        toast.success(`${productName} rejeitado`);
        onAction();
      } else {
        toast.error('Registro de quarentena nao encontrado');
      }
    } catch {
      toast.error('Falha ao rejeitar');
    } finally {
      setBusy(false);
      setConfirmingReject(false);
    }
  }

  return (
    <div className="sticky bottom-0 px-6 py-4 bg-white border-t border-ink/10 flex items-center gap-3">
      <Button onClick={handleApprove} disabled={busy} className="flex-1">
        {busy ? 'Processando...' : 'Aprovar'}
      </Button>
      <Button
        variant={confirmingReject ? 'destructive' : 'outline'}
        onClick={handleReject}
        onBlur={() => setConfirmingReject(false)}
        disabled={busy}
        className="flex-1"
      >
        {confirmingReject ? 'Confirmar Rejeicao' : 'Rejeitar'}
      </Button>
    </div>
  );
}
```

- [ ] **Step 5: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/products/ProductSheet.tsx
git commit -m "feat: enhance ProductSheet with status indicators, collapsed default, quarantine actions"
```

---

## Chunk 6: Navigation + Routes

### Task 13: Simplify navigation in Layout.tsx

**Files:**
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Replace nav items and remove quarantine polling**

Replace the `mainNavItems` and `adminNavItems` arrays with a single nav array:

```typescript
const navItems = [
  { to: '/', label: 'Home', icon: homeIcon },
  { to: '/brands', label: 'Brands', icon: brandsIcon },
  { to: '/explorer', label: 'Explorador', icon: productIcon },
];
```

Remove:
- The `adminNavItems` array entirely
- The `quarantineCount` state and `fetchQuarantineCount` callback
- The `useEffect` that polls quarantine count (lines 91-104)
- The `import { getQuarantine } from '@/lib/api'`

Update the nav JSX to render only `navItems` — remove the separator div and the admin nav loop:

```tsx
<nav className="flex items-center gap-0">
  {navItems.map((item, i) => (
    <motion.div
      key={item.to}
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 + i * 0.05 }}
    >
      <NavLink
        to={item.to}
        end={item.to === '/'}
        className={({ isActive }) =>
          cn(
            'relative flex items-center gap-2 px-4 py-2 text-sm transition-colors duration-200',
            isActive
              ? 'text-champagne-dark font-medium'
              : 'text-ink-muted hover:text-ink'
          )
        }
      >
        {({ isActive }) => (
          <>
            <item.icon />
            <span>{item.label}</span>
            {isActive && (
              <motion.div
                layoutId="nav-underline"
                className="absolute bottom-0 left-2 right-2 h-0.5 bg-champagne rounded-full"
                transition={{ type: 'spring', stiffness: 380, damping: 30 }}
              />
            )}
          </>
        )}
      </NavLink>
    </motion.div>
  ))}
</nav>
```

Remove unused icon functions: `dashboardIcon`, `quarantineIcon`, `reviewQueueIcon`. Keep `homeIcon`, `brandsIcon`, `productIcon`.

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Layout.tsx
git commit -m "feat: simplify nav to Home, Brands, Explorador — remove admin section and quarantine polling"
```

### Task 14: Update routes in App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Update routes**

```tsx
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import BrandsDashboard from './pages/BrandsDashboard'
import BrandPage from './pages/BrandPage'
import ProductDetail from './pages/ProductDetail'
import ProductBrowser from './pages/ProductBrowser'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        {/* Main routes */}
        <Route index element={<Home />} />
        <Route path="brands" element={<BrandsDashboard />} />
        <Route path="brands/:slug" element={<BrandPage />} />
        <Route path="brands/:slug/products/:productId" element={<ProductDetail />} />
        <Route path="explorer" element={<ProductBrowser />} />

        {/* Redirects from old routes */}
        <Route path="admin" element={<Navigate to="/" replace />} />
        <Route path="admin/products" element={<Navigate to="/explorer" replace />} />
        <Route path="admin/quarantine" element={<Navigate to="/" replace />} />
        <Route path="admin/review-queue" element={<Navigate to="/" replace />} />
        <Route path="products" element={<Navigate to="/explorer" replace />} />
        <Route path="quarantine" element={<Navigate to="/" replace />} />
        <Route path="review-queue" element={<Navigate to="/" replace />} />
        <Route path="brand-detail/:slug" element={<Navigate to="/brands/:slug" replace />} />
      </Route>
    </Routes>
  )
}

export default App
```

Note: Remove imports for `Dashboard`, `QuarantineReview`, `ReviewQueue`, `BrandDetail` as they are no longer directly used in routes. The files can stay for now (they may be useful for reference or future features).

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: update routes — add /explorer, redirect old admin routes"
```

---

## Chunk 7: Build Verification + Final Polish

### Task 15: Full build verification and fix any issues

**Files:**
- All modified files

- [ ] **Step 1: Run TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors. Fix any type errors found.

- [ ] **Step 2: Run build**

Run: `cd frontend && npm run build`
Expected: Build succeeds. Fix any errors.

- [ ] **Step 3: Run lint**

Run: `cd frontend && npm run lint`
Expected: No critical errors. Fix any that appear.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A frontend/src/
git commit -m "fix: resolve build errors from quick polish implementation"
```

### Task 16: Test locally

- [ ] **Step 1: Start dev server**

Run: `cd frontend && npm run dev`

Verify the following manually:
1. Home page shows health score, attention alerts, sorted brand grid
2. Click a brand → tabs show (Produtos, Quarentena, Cobertura)
3. Quarentena tab shows inline items with approve/reject
4. Cobertura tab shows coverage funnel
5. Navigation shows only Home | Brands | Explorador
6. `/admin` redirects to `/`
7. `/admin/products` redirects to `/explorer`
8. ProductSheet opens with sections collapsed, status indicators visible
9. Brand cards show red quarantine dot where applicable

- [ ] **Step 2: Fix any visual issues found**

- [ ] **Step 3: Final commit**

```bash
git add -A frontend/src/
git commit -m "fix: visual polish and adjustments from local testing"
```
