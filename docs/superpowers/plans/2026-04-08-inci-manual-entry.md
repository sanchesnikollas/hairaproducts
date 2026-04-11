# INCI Manual Entry Workflow — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a dedicated ops workflow for Clarisse and Fernanda to manually enter INCI composition from physical product packaging, targeting ~1,000 products across 6 priority brands.

**Architecture:** New API endpoint for INCI pending summary per brand + verification_status filter on existing product list + new dedicated frontend page `OpsInciEntry.tsx` with streamlined UX. When INCI is manually saved, backend auto-upgrades `verification_status` to `verified_inci`.

**Tech Stack:** Python/FastAPI (backend), React/TypeScript/Tailwind (frontend), SQLAlchemy ORM.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `src/api/routes/ops.py` | Add verification_status filter, INCI summary endpoint, auto-upgrade logic on PATCH |
| Modify | `frontend/src/lib/ops-api.ts` | Add API client functions for new endpoints |
| Create | `frontend/src/pages/ops/OpsInciEntry.tsx` | Dedicated INCI entry page with brand selector + product queue + inline editor |
| Modify | `frontend/src/App.tsx` | Add route for `/ops/inci` |
| Modify | `frontend/src/components/ops/OpsLayout.tsx` | Add nav link for INCI entry |

---

### Task 1: Backend — Add verification_status filter + INCI summary endpoint

**Files:**
- Modify: `src/api/routes/ops.py:95-106` (OpsProductUpdate model)
- Modify: `src/api/routes/ops.py:128-176` (ops_list_products endpoint)
- Modify: `src/api/routes/ops.py:314-331` (ops_patch_product endpoint)

- [ ] **Step 1: Add verification_status filter to product list endpoint**

In `ops_list_products`, add a `verification_status` query parameter:

```python
@router.get("/products")
def ops_list_products(
    brand: str | None = None,
    status_editorial: str | None = None,
    verification_status: str | None = None,  # NEW
    search: str | None = None,
    page: int = 1,
    per_page: int = 30,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    q = session.query(ProductORM)
    if brand:
        q = q.filter(ProductORM.brand_slug == brand)
    if status_editorial:
        q = q.filter(ProductORM.status_editorial == status_editorial)
    if verification_status:
        q = q.filter(ProductORM.verification_status == verification_status)
    if search:
        q = q.filter(ProductORM.product_name.ilike(f"%{search}%"))
    # ... rest unchanged
```

- [ ] **Step 2: Fix inci_ingredients type in OpsProductUpdate**

Change from `str | None` to `list[str] | None`:

```python
class OpsProductUpdate(BaseModel):
    product_name: str | None = None
    description: str | None = None
    usage_instructions: str | None = None
    composition: str | None = None
    inci_ingredients: list[str] | None = None  # Changed from str
    product_category: str | None = None
    size_volume: str | None = None
    status_editorial: StatusEditorial | None = None
    status_publicacao: StatusPublicacao | None = None
    status_operacional: StatusOperacional | None = None
```

- [ ] **Step 3: Auto-upgrade verification_status when INCI is manually entered**

In `ops_patch_product`, after applying updates, check if inci_ingredients was set and auto-upgrade:

```python
@router.patch("/products/{product_id}")
def ops_patch_product(
    product_id: str,
    body: OpsProductUpdate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    product = session.query(ProductORM).filter(ProductORM.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    updates = body.model_dump(exclude_none=True)
    old_values = {f: getattr(product, f) for f in updates}
    for field, value in updates.items():
        setattr(product, field, value)
    # Auto-upgrade: if inci_ingredients was set with content, mark as verified
    if "inci_ingredients" in updates and updates["inci_ingredients"]:
        if product.verification_status != "verified_inci":
            old_values["verification_status"] = product.verification_status
            product.verification_status = "verified_inci"
            updates["verification_status"] = "verified_inci"
    create_revisions(session, "product", product_id, old_values, updates, user["sub"], "human")
    _recalculate_confidence(session, product)
    session.commit()
    return {"status": "ok", "product_id": product_id, "confidence": product.confidence}
```

- [ ] **Step 4: Add INCI summary endpoint**

Add new endpoint that returns count of catalog_only products per brand, for the brand selector:

```python
@router.get("/inci-summary")
def inci_summary(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    results = (
        session.query(
            ProductORM.brand_slug,
            func.count(ProductORM.id).label("total"),
            func.sum(case((ProductORM.verification_status == "catalog_only", 1), else_=0)).label("pending"),
            func.sum(case((ProductORM.verification_status == "verified_inci", 1), else_=0)).label("verified"),
        )
        .group_by(ProductORM.brand_slug)
        .order_by(func.sum(case((ProductORM.verification_status == "catalog_only", 1), else_=0)).desc())
        .all()
    )
    return {
        "brands": [
            {
                "brand_slug": r.brand_slug,
                "total": r.total,
                "pending": r.pending,
                "verified": r.verified,
                "pct": round(r.verified / r.total * 100, 1) if r.total > 0 else 0,
            }
            for r in results
        ],
        "total_pending": sum(r.pending for r in results),
    }
```

- [ ] **Step 5: Test backend changes manually**

Run: `uvicorn src.api.main:app --reload --port 8000`

Test:
```bash
# INCI summary
curl -s http://localhost:8000/api/ops/inci-summary -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Product list with verification_status filter
curl -s "http://localhost:8000/api/ops/products?verification_status=catalog_only&brand=eudora&per_page=2" -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

- [ ] **Step 6: Commit backend changes**

```bash
git add src/api/routes/ops.py
git commit -m "feat(api): add INCI manual entry support — summary endpoint, verification_status filter, auto-upgrade on INCI save"
```

---

### Task 2: Frontend — API client functions

**Files:**
- Modify: `frontend/src/lib/ops-api.ts`

- [ ] **Step 1: Add opsGetInciSummary and update opsListProducts params**

Add to `frontend/src/lib/ops-api.ts`:

```typescript
export interface InciSummaryBrand {
  brand_slug: string;
  total: number;
  pending: number;
  verified: number;
  pct: number;
}

export async function opsGetInciSummary(): Promise<{
  brands: InciSummaryBrand[];
  total_pending: number;
}> {
  const res = await authFetch(`${BASE}/ops/inci-summary`);
  return res.json();
}
```

Update `opsListProducts` params type to include `verification_status`:

```typescript
export async function opsListProducts(params?: {
  brand?: string;
  status_editorial?: string;
  verification_status?: string;
  search?: string;
  page?: number;
}): Promise<{ ... }> {
  const qs = new URLSearchParams();
  if (params?.brand) qs.set("brand", params.brand);
  if (params?.status_editorial) qs.set("status_editorial", params.status_editorial);
  if (params?.verification_status) qs.set("verification_status", params.verification_status);
  if (params?.search) qs.set("search", params.search);
  if (params?.page) qs.set("page", String(params.page));
  const res = await authFetch(`${BASE}/ops/products?${qs}`);
  return res.json();
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ops-api.ts
git commit -m "feat(frontend): add INCI summary API client + verification_status filter param"
```

---

### Task 3: Frontend — OpsInciEntry page

**Files:**
- Create: `frontend/src/pages/ops/OpsInciEntry.tsx`

This is the main deliverable. The page has 3 sections:

1. **Header bar** — title + total pending count
2. **Brand selector** — cards/list showing each brand with pending count, sorted by most pending
3. **Product queue** — when a brand is selected, shows catalog_only products with inline INCI entry

- [ ] **Step 1: Create OpsInciEntry.tsx with brand selector**

```tsx
import { useState, useCallback } from "react";
import { useAPI } from "../../hooks/useAPI";
import { opsGetInciSummary, opsListProducts, opsUpdateProduct } from "../../lib/ops-api";
import type { InciSummaryBrand } from "../../lib/ops-api";

export default function OpsInciEntry() {
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expandedProduct, setExpandedProduct] = useState<string | null>(null);
  const [inciText, setInciText] = useState("");
  const [saving, setSaving] = useState(false);

  const { data: summary, refetch: refetchSummary } = useAPI(opsGetInciSummary, []);

  const productFetcher = useCallback(
    () => selectedBrand
      ? opsListProducts({ brand: selectedBrand, verification_status: "catalog_only", page, per_page: 20 })
      : Promise.resolve(null),
    [selectedBrand, page],
  );
  const { data: products, loading: productsLoading, refetch: refetchProducts } = useAPI(productFetcher, [selectedBrand, page]);

  const handleSaveInci = async (productId: string) => {
    if (!inciText.trim()) return;
    setSaving(true);
    try {
      // Parse comma/semicolon separated INCI text into list
      const ingredients = inciText
        .split(/[,;]/)
        .map((s) => s.trim())
        .filter(Boolean);
      await opsUpdateProduct(productId, {
        inci_ingredients: ingredients,
        composition: inciText.trim(),
      });
      setExpandedProduct(null);
      setInciText("");
      refetchProducts();
      refetchSummary();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar INCI");
    } finally {
      setSaving(false);
    }
  };

  const priorityBrands = summary?.brands.filter((b) => b.pending > 0) ?? [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ink">Entrada INCI Manual</h1>
          <p className="text-sm text-ink-muted mt-1">
            Insira a composicao INCI a partir da embalagem fisica do produto
          </p>
        </div>
        {summary && (
          <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-2 text-center">
            <div className="text-2xl font-bold text-amber-700">{summary.total_pending}</div>
            <div className="text-xs text-amber-600">produtos pendentes</div>
          </div>
        )}
      </div>

      {/* Brand selector */}
      <div>
        <h2 className="text-sm font-semibold text-ink mb-3">Selecione a marca</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {priorityBrands.map((b: InciSummaryBrand) => (
            <button
              key={b.brand_slug}
              onClick={() => { setSelectedBrand(b.brand_slug); setPage(1); setExpandedProduct(null); }}
              className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                selectedBrand === b.brand_slug
                  ? "border-ink bg-ink text-white"
                  : "border-cream-dark bg-white hover:border-ink/30"
              }`}
            >
              <div className="text-sm font-medium truncate">{b.brand_slug}</div>
              <div className="flex items-center justify-between mt-1">
                <span className={`text-xs ${selectedBrand === b.brand_slug ? "text-white/70" : "text-amber-600"}`}>
                  {b.pending} pendentes
                </span>
                <span className={`text-xs ${selectedBrand === b.brand_slug ? "text-white/70" : "text-emerald-600"}`}>
                  {b.pct}%
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Product queue */}
      {selectedBrand && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-ink">
              {selectedBrand} — Produtos sem INCI
              {products && <span className="text-ink-muted font-normal ml-2">({products.total} total)</span>}
            </h2>
          </div>

          {productsLoading && <p className="text-ink-muted text-sm">Carregando...</p>}

          {products && products.items && (
            <>
              <div className="space-y-2">
                {products.items.map((p: { id: string; product_name: string; brand_slug: string; confidence: number }) => (
                  <div key={p.id} className="rounded-xl border border-cream-dark bg-white overflow-hidden">
                    {/* Product row */}
                    <button
                      onClick={() => {
                        if (expandedProduct === p.id) {
                          setExpandedProduct(null);
                          setInciText("");
                        } else {
                          setExpandedProduct(p.id);
                          setInciText("");
                        }
                      }}
                      className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-cream/50 transition-colors"
                    >
                      <div>
                        <span className="text-sm font-medium text-ink">{p.product_name}</span>
                        <span className="ml-2 text-xs text-ink-muted">{p.confidence}% confianca</span>
                      </div>
                      <svg
                        className={`w-4 h-4 text-ink-muted transition-transform ${expandedProduct === p.id ? "rotate-180" : ""}`}
                        fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>

                    {/* Expanded INCI entry */}
                    {expandedProduct === p.id && (
                      <div className="border-t border-cream-dark px-4 py-4 bg-cream/30">
                        <label className="block text-xs text-ink-muted mb-1">
                          Cole a composicao INCI da embalagem (ingredientes separados por virgula)
                        </label>
                        <textarea
                          value={inciText}
                          onChange={(e) => setInciText(e.target.value)}
                          rows={4}
                          placeholder="Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, ..."
                          className="w-full rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
                          autoFocus
                        />
                        {/* Preview */}
                        {inciText.trim() && (
                          <div className="mt-2">
                            <span className="text-xs text-ink-muted">
                              {inciText.split(/[,;]/).filter((s) => s.trim()).length} ingredientes detectados
                            </span>
                          </div>
                        )}
                        <div className="flex justify-end gap-2 mt-3">
                          <button
                            onClick={() => { setExpandedProduct(null); setInciText(""); }}
                            className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream"
                          >
                            Cancelar
                          </button>
                          <button
                            onClick={() => handleSaveInci(p.id)}
                            disabled={saving || !inciText.trim()}
                            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                          >
                            {saving ? "Salvando..." : "Salvar INCI"}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Pagination */}
              {products.total > 20 && (
                <div className="flex items-center justify-between mt-4 text-sm text-ink-muted">
                  <span>{products.total} produtos</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50"
                    >
                      Anterior
                    </button>
                    <span className="flex items-center px-2">Pagina {page}</span>
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      disabled={products.items.length < 20}
                      className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50"
                    >
                      Proxima
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/ops/OpsInciEntry.tsx
git commit -m "feat(frontend): add OpsInciEntry page for manual INCI data entry"
```

---

### Task 4: Frontend — Wire up route and navigation

**Files:**
- Modify: `frontend/src/App.tsx:41` (add route)
- Modify: `frontend/src/components/ops/OpsLayout.tsx` (add nav link)

- [ ] **Step 1: Add route in App.tsx**

Add inside the `/ops` route group, after the `ingredients` route:

```tsx
import OpsInciEntry from './pages/ops/OpsInciEntry'

// Inside <Route path="/ops" element={<OpsLayout />}>:
<Route path="inci" element={<OpsInciEntry />} />
```

- [ ] **Step 2: Add nav link in OpsLayout.tsx**

Add "INCI" nav item to the sidebar/nav, between "Ingredientes" and "Settings":

```tsx
{ path: "/ops/inci", label: "INCI Manual" }
```

- [ ] **Step 3: Test the full flow**

Run both servers:
```bash
# Terminal 1
uvicorn src.api.main:app --reload --port 8000

# Terminal 2
cd frontend && npm run dev
```

Navigate to `http://localhost:5173/ops/inci` and verify:
1. Brand cards load with pending counts
2. Clicking a brand loads catalog_only products
3. Expanding a product shows the INCI textarea
4. Entering INCI text and saving updates the product
5. Product disappears from the queue after save (now verified_inci)
6. Pending count decreases

- [ ] **Step 4: Build check**

```bash
cd frontend && npm run build
```

Expected: no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/ops/OpsLayout.tsx
git commit -m "feat(frontend): wire up INCI manual entry route and navigation"
```

---

### Task 5: Backend — Add per_page to product list for INCI page

**Files:**
- Modify: `src/api/routes/ops.py:128-176`

The INCI page uses `per_page=20` but the existing endpoint doesn't forward this param from the client properly (the `opsListProducts` function doesn't pass it). This task ensures the page size is respected.

- [ ] **Step 1: Verify per_page works in the endpoint**

The endpoint already accepts `per_page` as a parameter. Just need to make sure the frontend passes it.

Update `opsListProducts` in `frontend/src/lib/ops-api.ts` to forward `per_page`:

```typescript
export async function opsListProducts(params?: {
  brand?: string;
  status_editorial?: string;
  verification_status?: string;
  search?: string;
  page?: number;
  per_page?: number;
}): Promise<...> {
  const qs = new URLSearchParams();
  // ... existing params ...
  if (params?.per_page) qs.set("per_page", String(params.per_page));
  // ...
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/ops-api.ts
git commit -m "feat(frontend): pass per_page param in opsListProducts"
```
