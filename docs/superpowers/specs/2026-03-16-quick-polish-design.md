# HAIRA Quick Polish — Design Specification

**Date:** 2026-03-16
**Status:** Approved
**Scope:** Improve the HAIRA web experience for project owners validating the data base

---

## 1. Context

HAIRA web is a validation tool for project stakeholders. They use it to verify data quality, review quarantined products, and audit coverage before integrating the database into the consumer app. The current frontend is technically polished (Shadcn, Motion, Recharts) but optimized for browsing, not for fast validation workflows.

**Target user:** Project owners validating the base
**Success criteria:** Open HAIRA → understand health in 3 seconds → act on issues → get back to pipeline work
**Constraints:** Minimal effort (1-2 sessions), no new frontend dependencies (Sonner toast library already installed via Shadcn), no backend changes beyond what's already deployed

---

## 2. Home — Health Dashboard

### Current State
Hero section with decorative text, stats bar (products, brands, ingredients, avg INCI), brand grid with cards.

### Changes

**Remove:**
- Hero text ("Base de conhecimento de produtos capilares")
- Decorative stats bar (redundant with health score)

**Add:**

**Health Score (top of page)**
- Large percentage number: computed client-side from `/api/brands` response by weighting each brand's `inci_rate` by its `product_count`
- Formula: `sum(brand.inci_rate * brand.product_count) / sum(brand.product_count)`
- Color: green (≥80%), amber (50-79%), red (<50%)
- Subtitle: "X produtos, Y marcas, Z% INCI médio"
- Note: `/api/brands` returns different shapes in multi-DB vs single-DB mode. Use `product_count`/`inci_rate` (multi-DB) or `verified_inci_rate`/`extracted_total` (single-DB). Current Home.tsx already handles this with a `BrandItem` union type — follow that pattern

**Attention Alerts (below score)**
- Horizontal row of clickable badges, only shown when there are issues:
  - "N em quarentena" (links to first brand with pending quarantine)
  - "N marcas <50% INCI" (links to brands page filtered)
  - Per-brand alerts for brands with significant gaps (e.g., "Redken: 36 sem INCI")
- Empty state: green checkmark "Base saudável — nenhum alerta"

**Brand Grid (below alerts)**
- Keep existing BrandCard component but enhance:
  - INCI rate bar uses semaphore colors (green/amber/red)
  - Badge overlay if brand has pending quarantine items (small red dot)
  - Sort by: brands needing attention first (lowest INCI rate, most quarantine items)

### Data Source
- Health score and alerts computed from `/api/stats` + `/api/brands` + `/api/quarantine?review_status=pending` (all already available)
- No new backend endpoints needed

---

## 3. Brand Page — Single-Page Validation

### Current State
Brand header + search + filters + product grid + pagination. Quarantine and coverage live in separate admin pages.

### Changes

**Header (compacted)**
- Brand name, platform badge, INCI rate as large number with semaphore color
- Inline counters: "X produtos · Y verificados · Z quarentena"
- Remove redundant stats grid below header

**Tabs: Produtos | Quarentena | Cobertura**
All within the brand page, no navigation to external admin routes.

**Tab: Produtos (default)**
- Current product grid with visual status indicators:
  - Green left border: verified_inci
  - Amber left border: catalog_only
  - Red left border: quarantined
- Click opens product detail sheet (existing behavior, enhanced per Section 4)
- Keep existing filters (search, category, verified-only)

**Tab: Quarentena**
- List of quarantined products for THIS brand only
- Each item shows: product name, rejection reason badge, rejection code
- Inline actions: Approve button (no confirmation), Reject button (requires click to confirm)
- No expand/collapse — all info visible at a glance
- Item animates out on action, counter in tab badge decrements

**Tab: Cobertura**
- Coverage funnel: Discovered → Hair Products → Extracted → Verified INCI
- Horizontal bar segments with labels and counts
- Compact: fits in ~200px height

### Data Source
- Products: `/api/brands/{slug}/products` (existing)
- Quarantine: `/api/quarantine?brand={slug}&review_status=pending` (existing, multi-DB aware — the `brand` query param routes to the brand's DB via `_get_session` dependency)
- Coverage: `/api/brands/{slug}/coverage` (existing)

---

## 4. Product Detail Sheet — Quick Validation

### Current State
Sheet opens with product data but dense, no visual hierarchy for validation.

### Changes

**Top: Quality Score**
- Large badge: score number + color (green 100, amber ≥70, red <70)
- If issues exist, list them as small text below the score

**Status + Seals Row**
- Verification status badge (verified/catalog_only/quarantined)
- Seal badges split: detected (solid fill) vs inferred (outline/dashed border)

**Collapsible Sections with Status Icons**
Each section has a status indicator in the header:
- ✓ green check: field populated
- ⚠ amber warning: field empty/missing
- Sections: INCI Ingredients, Descrição, Composição, Modo de Uso

Default state: all collapsed. Click to expand.

**INCI Section (when expanded)**
- Numbered ingredient list
- Color highlights: silicones (orange), sulfates (red) — existing logic from ProductDetail page
- Count badge: "N ingredientes"

**Evidence Summary**
- Single line: "Extraído via {method} em {date}"
- Expandable to full evidence table if needed

**Footer Actions (if quarantined)**
- Approve / Reject buttons pinned to bottom of sheet
- Same behavior as quarantine tab actions

---

## 5. Navigation Simplification

### Current State
Header has two nav sections: Main (Home, Brands) + Admin (Dashboard, Products, Quarantine, Review Queue) separated by a divider.

### Changes

**Remove from nav:**
- Dashboard link (Home replaces it)
- Quarantine link (lives inside brand pages now)
- Review Queue link (lives inside brand pages now)

**Quarantine badge relocation:** The current Layout.tsx polls `/api/quarantine?review_status=pending` every 60s to show a count badge on the Quarantine nav item. Remove this polling from Layout. Instead, the Home page's AttentionAlerts component fetches quarantine count on mount (not polling — stale data is fine for the home page). The badge now appears as an alert on the Home page, not in the nav.

**Keep in nav:**
- Home
- Brands
- Explorador (renamed from Products — cross-brand product table with brand selector dropdown)

**Nav structure:** `Home | Brands | Explorador`

**Cmd+K Search:** Keep existing GlobalSearch component as-is. No enhancements in this phase — the existing brand/product search is sufficient. Enhancements (quarantine navigation, cross-brand search) deferred to a follow-up.

### Routes After Change
| Route | Page | Description |
|-------|------|-------------|
| `/` | Home | Health dashboard |
| `/brands` | Brand Catalog | Grid of all brands |
| `/brands/:slug` | Brand Page | Tabs: Produtos, Quarentena, Cobertura |
| `/brands/:slug/products/:productId` | Product Detail | Full page (for direct links) |
| `/explorer` | Product Explorer | Cross-brand product table with brand selector |

**Removed routes** (redirect to new locations):
- `/admin` → `/`
- `/admin/products` → `/explorer`
- `/admin/quarantine` → `/` (home alerts)
- `/admin/review-queue` → `/` (home alerts)

---

## 6. Micro-interactions and Feedback

### Contextual Toasts
- On approve: "Produto X aprovado — N restantes em quarentena"
- On reject: "Produto X rejeitado"
- Include product name, not just generic "Approved"

### Exit Animations
- Approved/rejected items: fade + slide-right out, list compacts smoothly
- Use existing Motion library, `layout` prop for list reflow

### Keyboard Shortcuts (Phase 2 — deferred)
Keyboard shortcuts (A/R for approve/reject, arrow navigation) deferred to follow-up. Focus management and conflict avoidance with Cmd+K requires careful implementation that doesn't fit the quick polish scope.

### Session Progress
- When reviewing quarantine for a brand, show progress bar: "N/M revisados"
- Thin bar at top of the quarantine tab content area
- Disappears when all items reviewed, replaced by "Tudo revisado ✓"

### Confirmation Logic
- Approve: instant, no confirmation (safe action — can be reversed)
- Reject: single extra click to confirm (destructive)

---

## 7. What Does NOT Change

- **Design system**: colors, typography, spacing — all stay the same
- **Component library**: Shadcn components, existing Button/Card/Badge/etc.
- **Animation library**: Motion (motion/react) — already in use
- **Backend**: No new endpoints. All data already available from existing API. Minor backend fix may be needed for quarantine approve/reject to work with `brand` query param routing in multi-DB mode (already partially implemented)
- **Product Detail full page** (`/brands/:slug/products/:id`): Stays for direct linking, enhanced to match sheet improvements
- **Global Search (Cmd+K)**: Stays as-is, enhancements deferred

---

## 8. Implementation Approach

This is a frontend-only change. The backend multi-DB architecture already supports all required data access patterns.

**Key files to modify:**
- `frontend/src/pages/Home.tsx` — replace hero with health dashboard
- `frontend/src/pages/BrandPage.tsx` — add tabs (Quarentena, Cobertura), compact header
- `frontend/src/components/products/ProductSheet.tsx` — add quality score, collapsible sections, footer actions
- `frontend/src/components/Layout.tsx` — simplify nav
- `frontend/src/App.tsx` — update routes, add redirects
- `frontend/src/lib/api.ts` — minor: add helper for quarantine by brand

**New components:**
- `HealthScore.tsx` — the global health score with semaphore color
- `AttentionAlerts.tsx` — clickable alert badges
- `QuarantineTab.tsx` — inline quarantine review within brand page
- `CoverageTab.tsx` — compact coverage funnel
- `SessionProgress.tsx` — thin progress bar for review sessions

**Components to enhance (not rewrite):**
- `BrandCard.tsx` — add quarantine dot, semaphore color on INCI bar
- `SealBadge.tsx` — add outline variant for inferred seals
- `ProductCard.tsx` — add left border color by status
