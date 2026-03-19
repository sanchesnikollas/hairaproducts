# HAIRA Frontend Redesign — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform HAIRA from a raw dashboard into a premium SaaS analyst tool using Shadcn/UI with the existing HAIRA color palette.

**Architecture:** Install Shadcn/UI on Tailwind v4, map HAIRA palette (champagne, sage, coral, cream, ink) to Shadcn CSS variables. Incrementally replace custom components with Shadcn equivalents, then redesign each page (Dashboard, Products, Quarantine) following the approved design doc at `docs/plans/2026-03-10-frontend-redesign-design.md`.

**Tech Stack:** React 19, Tailwind CSS v4, Shadcn/UI, Radix UI, Sonner (toasts), Motion, Recharts, cmdk (Command menu)

---

## Task 1: Setup Shadcn/UI + Path Aliases

**Files:**
- Modify: `frontend/tsconfig.json`
- Modify: `frontend/tsconfig.app.json`
- Modify: `frontend/vite.config.ts`
- Create: `frontend/components.json`
- Create: `frontend/src/lib/utils.ts`

**Step 1: Install dependencies**

```bash
cd frontend
npm install tailwindcss-animate class-variance-authority clsx tailwind-merge
npm install -D @types/node
```

**Step 2: Add path aliases to tsconfig.app.json**

Add to `compilerOptions`:
```json
"baseUrl": ".",
"paths": {
  "@/*": ["./src/*"]
}
```

**Step 3: Add path aliases to vite.config.ts**

```ts
import path from "path"
// add to defineConfig:
resolve: {
  alias: {
    "@": path.resolve(__dirname, "./src"),
  },
},
```

**Step 4: Create utils.ts**

```ts
// frontend/src/lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

**Step 5: Initialize Shadcn**

```bash
cd frontend
npx shadcn@latest init
```

Select: New York style, Zinc base color, CSS variables yes. Then manually update the generated CSS variables to match HAIRA palette in `frontend/src/index.css`.

**Step 6: Map HAIRA palette to Shadcn CSS variables**

In `frontend/src/index.css`, update the `:root` / `@layer base` block that Shadcn creates. Keep existing HAIRA `@theme` tokens AND add Shadcn's expected variables mapped to HAIRA colors:

```css
:root {
  --background: 37 33% 97%;       /* cream #FAF7F2 */
  --foreground: 24 12% 9%;        /* ink #1A1714 */
  --card: 0 0% 100%;              /* white */
  --card-foreground: 24 12% 9%;   /* ink */
  --popover: 0 0% 100%;
  --popover-foreground: 24 12% 9%;
  --primary: 37 44% 61%;          /* champagne #C9A96E */
  --primary-foreground: 0 0% 100%;
  --secondary: 125 15% 55%;       /* sage #7A9E7E */
  --secondary-foreground: 0 0% 100%;
  --muted: 24 10% 68%;            /* ink-faint #B8AFA6 */
  --muted-foreground: 24 10% 45%; /* ink-muted #7A7068 */
  --accent: 37 33% 93%;           /* cream-dark #F0EBE3 */
  --accent-foreground: 24 12% 9%;
  --destructive: 14 36% 59%;      /* coral #C27C6B */
  --destructive-foreground: 0 0% 100%;
  --border: 24 12% 9% / 0.1;      /* ink/10 */
  --input: 24 12% 9% / 0.1;
  --ring: 37 44% 61%;             /* champagne */
  --radius: 0.5rem;
}
```

**Step 7: Verify build**

```bash
cd frontend && npm run build
```

**Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: setup Shadcn/UI with HAIRA palette mapping"
```

---

## Task 2: Install Core Shadcn Components

**Files:**
- Create: `frontend/src/components/ui/button.tsx` (and other ui/ files)

**Step 1: Install Shadcn components**

```bash
cd frontend
npx shadcn@latest add button badge input tabs table skeleton tooltip sheet dialog dropdown-menu select command separator card scroll-area
```

**Step 2: Install Sonner for toasts**

```bash
cd frontend
npm install sonner
```

**Step 3: Add Toaster to main.tsx**

In `frontend/src/main.tsx`, add:
```tsx
import { Toaster } from 'sonner'
// Inside the app root, add <Toaster /> alongside <App />
```

**Step 4: Verify build**

```bash
cd frontend && npm run build
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: install core Shadcn components and Sonner toasts"
```

---

## Task 3: Redesign Layout & Navigation

**Files:**
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

**Step 1: Redesign Layout.tsx**

Replace current Layout with Shadcn-powered version:
- Sticky header with backdrop blur (keep existing)
- Nav items using Shadcn-style tabs with animated active indicator underline
- Badge counter on Quarantine nav item (fetch pending count from API)
- Sonner Toaster in layout root
- Global Command menu (Cmd+K) trigger in header

Key changes:
- Replace raw `<a>` nav links with styled NavLink components using `cn()` for active states
- Add `Badge` component next to "Quarantine" showing pending count
- Add keyboard shortcut listener for Cmd+K to open Command dialog
- Keep Motion animations for page transitions

**Step 2: Create global Command menu component**

Create `frontend/src/components/GlobalSearch.tsx`:
- Uses Shadcn Command + Dialog
- Fetches products on search input
- Navigate to product on select
- Keyboard shortcut Cmd+K to open

**Step 3: Verify build and test navigation**

```bash
cd frontend && npm run build
```

**Step 4: Commit**

```bash
git add frontend/src/components/Layout.tsx frontend/src/components/GlobalSearch.tsx frontend/src/App.tsx
git commit -m "feat: redesign navigation with Shadcn tabs, badges, and global search"
```

---

## Task 4: Redesign Dashboard

**Files:**
- Modify: `frontend/src/pages/Dashboard.tsx`

**Step 1: Redesign KPI cards section**

Replace current stat cards with Shadcn Card components:
- 4-column grid: Total Produtos, Verified INCI, Catalog Only, Quarantined
- Each card: large number in Cormorant font, percentage badge, subtle icon
- Skeleton loader while data loads
- Hover: shadow-sm -> shadow-md transition

**Step 2: Redesign charts section**

Middle 2-column layout:
- Left (2/3): Coverage funnel as horizontal bar chart (recharts BarChart)
- Right (1/3): Category distribution donut (recharts PieChart) with interactive legend

Bottom 2-column layout:
- Left: Quality seals horizontal bar chart with Shadcn Badges
- Right: Quick action Shadcn Cards with Button links to Products and Quarantine

**Step 3: Add Skeleton loading states**

Replace current LoadingState spinner usage with Shadcn Skeleton components matching the layout shape.

**Step 4: Verify build**

```bash
cd frontend && npm run build
```

**Step 5: Commit**

```bash
git add frontend/src/pages/Dashboard.tsx
git commit -m "feat: redesign Dashboard with Shadcn cards, skeletons, and improved charts"
```

---

## Task 5: Redesign Products Page — DataTable + Filters

**Files:**
- Create: `frontend/src/components/products/ProductsTable.tsx`
- Create: `frontend/src/components/products/ProductFilters.tsx`
- Create: `frontend/src/components/products/ProductSheet.tsx`
- Create: `frontend/src/components/products/columns.tsx`
- Modify: `frontend/src/pages/ProductBrowser.tsx`

**Step 1: Create column definitions**

`frontend/src/components/products/columns.tsx`:
- Define DataTable columns: thumbnail (40x40), product name, category, status (Badge), INCI count, quality score (mini ProgressBar)
- Sortable headers on name, category, status, quality

**Step 2: Create ProductFilters component**

`frontend/src/components/products/ProductFilters.tsx`:
- Shadcn Tabs for status filter (All | Verified | Catalog Only | Quarantined) with counter Badges
- Shadcn Input for search (with search icon)
- Shadcn Select for category filter
- Shadcn DropdownMenu for extra filters (exclude kits, has errors, warnings)

**Step 3: Create ProductSheet component**

`frontend/src/components/products/ProductSheet.tsx`:
- Shadcn Sheet (opens from right)
- Collapsible sections using Shadcn Separator + expand/collapse
- Basic Info section: name, brand, URL, image, category, type
- INCI section: ingredient list as inline Badges/chips
- Seals section: detected + inferred labels as colored Badges
- Evidence section: list of sources with URLs
- Edit section: inline form fields with Shadcn Input, Select, Button
- Action buttons: Save (champagne), Approve (sage), Reject (coral)
- Toast on action completion

**Step 4: Create ProductsTable component**

`frontend/src/components/products/ProductsTable.tsx`:
- Shadcn Table with sorting
- Row click opens ProductSheet
- Hover state on rows
- Pagination footer: "Showing X-Y of Z products"
- Skeleton rows while loading

**Step 5: Rewrite ProductBrowser page**

`frontend/src/pages/ProductBrowser.tsx`:
- Compose: ProductFilters + ProductsTable + ProductSheet
- Manage state: selected product, filters, pagination
- Keep existing API hooks but restructure data flow

**Step 6: Verify build**

```bash
cd frontend && npm run build
```

**Step 7: Commit**

```bash
git add frontend/src/components/products/ frontend/src/pages/ProductBrowser.tsx
git commit -m "feat: redesign Products with DataTable, filters, and side panel Sheet"
```

---

## Task 6: Redesign Quarantine Page

**Files:**
- Modify: `frontend/src/pages/QuarantineReview.tsx`

**Step 1: Redesign with Shadcn components**

- Top: Shadcn Tabs (Pending | Approved | Rejected) with counter Badges
- Replace current expandable list with Shadcn Card-based layout
- Each card: product thumbnail, name, rejection reason as coral Badge, rejection code
- Expand shows: evidence details, source URL, reviewer notes
- Inline actions: Button "Approve" (sage variant) + Button "Reject" (coral variant) + Input for notes
- Toast (Sonner) on approve/reject
- Card animates out (Motion) after action
- Skeleton cards while loading
- Empty state when no items in current tab

**Step 2: Verify build**

```bash
cd frontend && npm run build
```

**Step 3: Commit**

```bash
git add frontend/src/pages/QuarantineReview.tsx
git commit -m "feat: redesign Quarantine with Shadcn cards, tabs, and inline actions"
```

---

## Task 7: Update Shared Components + Cleanup

**Files:**
- Modify: `frontend/src/components/StatusBadge.tsx`
- Modify: `frontend/src/components/ProgressBar.tsx`
- Modify: `frontend/src/components/LoadingState.tsx`

**Step 1: Replace StatusBadge with Shadcn Badge**

Refactor StatusBadge to use Shadcn Badge internally with HAIRA color variants:
- verified_inci -> sage (secondary)
- catalog_only -> amber (outline)
- quarantined -> coral (destructive)

**Step 2: Update ProgressBar to use cn() utility**

Simplify with Tailwind classes and cn() for variants.

**Step 3: Update LoadingState to use Skeleton**

Replace spinner with Shadcn Skeleton components.

**Step 4: Remove unused components/styles from index.css**

Clean up any CSS that was replaced by Shadcn components.

**Step 5: Full build + visual check**

```bash
cd frontend && npm run build
```

**Step 6: Commit**

```bash
git add frontend/src/
git commit -m "feat: update shared components to use Shadcn, cleanup unused styles"
```

---

## Task 8: Final Polish + Deploy

**Files:**
- Modify: various frontend files for polish

**Step 1: Visual polish pass**

- Ensure consistent spacing across all pages
- Check all Skeleton loaders render correct shapes
- Verify all Toast messages show correctly
- Check Command menu (Cmd+K) works from all pages
- Test all filters and pagination on Products page
- Test approve/reject flow on Quarantine page

**Step 2: Build and verify**

```bash
cd frontend && npm run build
```

**Step 3: Commit and deploy**

```bash
git add frontend/
git commit -m "feat: final visual polish for frontend redesign"
railway service haira-app && railway up -d
```

---

## Execution Notes

- Each task should be verified with `npm run build` before committing
- The design doc at `docs/plans/2026-03-10-frontend-redesign-design.md` is the source of truth for visual decisions
- Keep Motion animations subtle — entrance animations only, no distracting loops
- All Shadcn components should use the HAIRA palette, not default Shadcn colors
- Test with real data from the production API (706 Amend products)
