# HAIRA Frontend Redesign — Design Document

**Date:** 2026-03-10
**Approach:** Shadcn/UI + Custom Design System Overhaul
**Goal:** Transform HAIRA from a raw dashboard into a premium SaaS tool for analysts to review, correct, and enrich product data.

## Target Users

Analysts and business stakeholders who need to:
- Review and validate product data (INCI, categories, labels)
- Approve/reject quarantined products
- Get a clear overview of data coverage and quality

## Foundation

### Stack
- Shadcn/UI components (Radix UI primitives)
- Tailwind CSS v4 (existing)
- Motion library (existing animations)
- Fonts: Cormorant Garamond (display) + DM Sans (body)

### Palette Mapping to Shadcn
- `--primary` -> champagne (#C9A96E)
- `--secondary` -> sage (#7A9E7E)
- `--destructive` -> coral (#C27C6B)
- `--warning` -> amber (#C9A040)
- `--background` -> cream (#FAF7F2)
- `--foreground` -> ink (#1A1714)
- `--muted` -> ink-faint (#B8AFA6)

### Shadcn Components to Install
Table, DataTable, Button, Input, Badge, Sheet, Dialog, Tabs, Tooltip, Toast (Sonner), Skeleton, Command, DropdownMenu, Select

## Dashboard

### KPI Cards (4 columns)
- Total Produtos | Verified INCI | Catalog Only | Quarantined
- Each: large number (Cormorant), percentage, subtle icon
- Shadcn Card with hover elevation

### Middle Section (2 columns)
- Left (2/3): Coverage funnel (Discovered -> Hair -> Extracted -> Verified) horizontal bar chart with labels and percentages between steps
- Right (1/3): Category distribution donut chart + interactive legend

### Bottom Section (2 columns)
- Left: Top quality seals (horizontal bar chart, Shadcn Badges)
- Right: Quick action cards — "Review Products", "Pending Quarantine" with counters and Shadcn Buttons

### Visual Changes
- Skeleton loaders instead of spinners
- Cards: subtle border + shadow-sm -> shadow-md on hover
- Toast (Sonner) for action feedback
- Motion animations maintained but more subtle

## Products — Analyst Work Interface

### Layout: Split View
- Left (list): Shadcn DataTable — columns: thumbnail, name, category, status Badge, INCI count, quality score
- Right (Sheet panel): Opens on product click, shows all details, allows inline editing

### Filter Bar (top)
- Shadcn Tabs for status (All | Verified | Catalog Only | Quarantined)
- Shadcn Command (Cmd+K search) for name/ingredient search
- Shadcn Select for category
- Shadcn DropdownMenu for extra filters (has errors, warnings, exclude kits)
- Counter badge next to each tab

### DataTable
- Sorting on all columns
- Row hover state (bg-cream-dark/50)
- Product thumbnail (40x40, rounded) first column
- Status as Shadcn Badge (sage=verified, amber=catalog, coral=quarantined)
- Quality score as inline mini ProgressBar
- Shadcn pagination footer: "Showing 1-100 of 276"

### Side Panel (Sheet)
- Opens from right on product click
- Collapsible sections: Basic Info, INCI Ingredients (chips), Detected Seals (badges), Evidence, Edit
- Action buttons: Save edit, Approve, Reject
- Toast confirmation after each action

### Empty/Loading States
- Skeleton rows in table while loading
- Empty state with subtle illustration + "No products found"

## Quarantine — Review Queue

### Layout
- Shadcn Tabs top: Pending | Approved | Rejected (with counter Badge)
- Card list (not table) — each item is a case to analyze

### Quarantine Card
- Shadcn Card: product name, thumbnail, rejection reason as coral Badge
- Rejection code highlighted
- Expand button -> shows evidence, source URL, notes
- Inline actions: "Approve" Button (sage) + "Reject" Button (coral) + notes Input
- Toast confirmation after action

### Visual Changes
- More spacious, readable cards
- Skeleton loaders
- Immediate visual feedback (card animates out after approve/reject)
- Counter updates in real-time on tab

## Global Layout & Navigation

### Header
- Keep sticky with backdrop blur
- HAIRA logo with Cormorant typography
- Nav with Shadcn Tabs style — animated active indicator
- Badge counter on Quarantine nav item when pending items exist

### Footer
- Minimalist, version + credit

### Global Features
- Sonner (Toast) provider at root for app-wide feedback
- Tooltips on icons and non-obvious actions
- Page transitions with Motion (fade in, keep existing)
- Global Command menu (Cmd+K) to search products from any page
