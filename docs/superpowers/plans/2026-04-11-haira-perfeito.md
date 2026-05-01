# HAIRA Perfeito — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate field validation, evidence tracking, photo upload improvements, bilingual INCI, seal detection, and dashboard UX into a polished production system.

**Architecture:** Most features already exist as isolated modules. This plan connects them: field_validator → ops PATCH, evidence → manual edits, label_engine → page text scanning, IngredientORM bilingual search. Frontend gets validation feedback, better filters, and quick-fill mode.

**Tech Stack:** Python/FastAPI, React/TypeScript, SQLAlchemy, Anthropic Vision API, Tailwind CSS

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `src/api/routes/ops.py` | Product CRUD + validation integration | Modify |
| `src/api/routes/ingredients.py` | Bilingual ingredient search | Modify |
| `src/core/field_validator.py` | Validation rules | Modify (add rules) |
| `src/core/label_engine.py` | Seal detection from page text | Modify |
| `src/storage/repository.py` | Ingredient search query | Modify |
| `frontend/src/pages/ops/OpsProductDetail.tsx` | Validation UI + photo UX | Modify |
| `frontend/src/pages/ops/OpsProducts.tsx` | Filters + quick-fill mode | Modify |
| `frontend/src/pages/ops/OpsDashboard.tsx` | Enhanced KPIs | Modify |

---

### Task 1: Integrate Field Validation into PATCH/POST

**Files:**
- Modify: `src/api/routes/ops.py:319-336` (ops_patch_product)
- Modify: `src/api/routes/ops.py:209-245` (ops_create_product)
- Existing: `src/core/field_validator.py:370` (validate_product_fields)

- [ ] **Step 1: Add validation call to ops_patch_product**

In `src/api/routes/ops.py`, after applying updates but before commit, call the validator:

```python
# In ops_patch_product, after line 332 (setattr loop), before _recalculate_confidence:
from src.core.field_validator import validate_product_fields

validation = validate_product_fields({
    "product_name": product.product_name,
    "brand_slug": product.brand_slug,
    "description": product.description,
    "inci_ingredients": product.inci_ingredients,
    "product_category": product.product_category,
    "price": product.price,
    "size_volume": product.size_volume,
    "product_url": product.product_url,
    "usage_instructions": product.usage_instructions,
})

# Block save if ERROR-level issues
if validation.error_count > 0:
    session.rollback()
    raise HTTPException(status_code=422, detail={
        "message": "Validation failed",
        "validation": validation.to_dict(),
    })
```

Modify return to include validation:
```python
return {
    "status": "ok",
    "product_id": product_id,
    "confidence": product.confidence,
    "validation": validation.to_dict(),
}
```

- [ ] **Step 2: Add same validation to ops_create_product**

Same pattern in the POST endpoint at line 209.

- [ ] **Step 3: Add product_name and category validation rules to field_validator.py**

In `src/core/field_validator.py`, add after existing rules:

```python
def _check_product_name(fields: dict) -> list[ValidationIssue]:
    issues = []
    name = fields.get("product_name", "")
    if not name or len(name.strip()) < 5:
        issues.append(ValidationIssue("product_name", "ERROR", "Nome muito curto (min 5 chars)"))
    generic = ["shampoo", "condicionador", "máscara", "conditioner"]
    if name.strip().lower() in generic:
        issues.append(ValidationIssue("product_name", "ERROR", "Nome genérico demais"))
    if name.startswith("http"):
        issues.append(ValidationIssue("product_name", "ERROR", "Nome parece uma URL"))
    return issues

def _check_category(fields: dict) -> list[ValidationIssue]:
    from src.core.taxonomy import VALID_CATEGORIES
    cat = fields.get("product_category")
    if cat and cat not in VALID_CATEGORIES and cat != "non_hair":
        return [ValidationIssue("product_category", "WARNING", f"Categoria '{cat}' não reconhecida")]
    return []

def _check_volume_format(fields: dict) -> list[ValidationIssue]:
    import re
    vol = fields.get("size_volume", "")
    if vol and not re.match(r'\d+(?:[.,]\d+)?\s*(?:ml|mL|g|kg|l|L|oz)', vol, re.IGNORECASE):
        return [ValidationIssue("size_volume", "INFO", "Formato de volume não padrão")]
    return []
```

Add to `validate_product_fields()` call chain.

- [ ] **Step 4: Run existing tests**

```bash
pytest tests/core/test_field_validator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/ops.py src/core/field_validator.py
git commit -m "feat: integrate field validation into product PATCH/POST endpoints"
```

---

### Task 2: Frontend Validation Feedback

**Files:**
- Modify: `frontend/src/pages/ops/OpsProductDetail.tsx`

- [ ] **Step 1: Handle 422 validation errors in save flow**

In `handleSave()`, after the API call:

```typescript
const handleSave = async () => {
    setSaving(true);
    try {
      // ... existing update logic ...
      const resp = await opsUpdateProduct(id!, updates);
      // Check if response has validation warnings
      if (resp?.validation?.warning_count > 0) {
        // Show warnings but save succeeded
        console.log("Warnings:", resp.validation.issues);
      }
      refetch();
    } catch (err: any) {
      if (err?.status === 422 && err?.detail?.validation) {
        // Show validation errors inline
        setValidationErrors(err.detail.validation.issues);
        return; // Don't close edit mode
      }
      alert(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };
```

- [ ] **Step 2: Add validation error display per field**

Add state and display component:

```typescript
const [validationErrors, setValidationErrors] = useState<Array<{field: string, severity: string, message: string}>>([]);

// Helper to get errors for a field
const fieldError = (field: string) => validationErrors.find(e => e.field === field && e.severity === 'ERROR');
const fieldWarning = (field: string) => validationErrors.find(e => e.field === field && e.severity === 'WARNING');

// In JSX, wrap inputs with error indicator:
// <input className={`${inputCls} ${fieldError('product_name') ? 'border-red-500' : ''}`} />
// {fieldError('product_name') && <p className="text-[10px] text-red-500 mt-0.5">{fieldError('product_name').message}</p>}
```

- [ ] **Step 3: Build and verify**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ops/OpsProductDetail.tsx
git commit -m "feat: show validation errors inline on product save"
```

---

### Task 3: Evidence Tracking on Manual Edits

**Files:**
- Modify: `src/api/routes/ops.py:319-336`
- Existing: `src/storage/orm_models.py:72-85` (ProductEvidenceORM)

- [ ] **Step 1: Create evidence records when INCI or key fields are manually edited**

In `ops_patch_product()`, after `create_revisions()` call:

```python
# Create evidence for manual edits
from src.storage.orm_models import ProductEvidenceORM
from datetime import datetime, timezone

evidence_fields = ["inci_ingredients", "description", "composition", "usage_instructions", "product_labels"]
for field in evidence_fields:
    if field in updates:
        evidence = ProductEvidenceORM(
            product_id=product_id,
            field_name=field,
            source_url=f"ops://manual/{user['sub']}",
            evidence_locator="ops_panel_edit",
            raw_source_text=str(updates[field])[:2000] if updates[field] else None,
            extraction_method="manual",
            extracted_at=datetime.now(timezone.utc),
        )
        session.add(evidence)
```

- [ ] **Step 2: Create evidence for photo-extracted data**

In the extract-from-photo apply flow, when the frontend saves data that came from a photo, the ops_patch_product will create evidence with extraction_method="manual". To distinguish photo origin, add a `source` field to OpsProductUpdate:

```python
class OpsProductUpdate(BaseModel):
    # ... existing fields ...
    _extraction_source: str | None = None  # "photo_vision", "manual", etc.
```

Then in ops_patch_product, use this source:

```python
extraction_method = body._extraction_source or "manual"
```

- [ ] **Step 3: Add endpoint to get product evidence**

```python
@router.get("/products/{product_id}/evidence")
def get_product_evidence(
    product_id: str,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_ops_session),
):
    from src.storage.orm_models import ProductEvidenceORM
    rows = session.query(ProductEvidenceORM).filter(
        ProductEvidenceORM.product_id == product_id
    ).order_by(ProductEvidenceORM.extracted_at.desc()).limit(50).all()
    return [
        {
            "field_name": e.field_name,
            "extraction_method": e.extraction_method,
            "source_url": e.source_url,
            "extracted_at": str(e.extracted_at) if e.extracted_at else None,
        }
        for e in rows
    ]
```

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/ops.py
git commit -m "feat: auto-create evidence records on manual product edits"
```

---

### Task 4: Bilingual Ingredient Search

**Files:**
- Modify: `src/storage/repository.py:270-276` (search_ingredients)
- Modify: `src/api/routes/ingredients.py:32-57`

- [ ] **Step 1: Update search_ingredients to search both fields**

In `src/storage/repository.py`, modify:

```python
def search_ingredients(self, query: str, limit: int = 50) -> list[IngredientORM]:
    from sqlalchemy import or_
    return (
        self._session.query(IngredientORM)
        .filter(or_(
            IngredientORM.canonical_name.ilike(f"%{query}%"),
            IngredientORM.inci_name.ilike(f"%{query}%"),
        ))
        .order_by(IngredientORM.canonical_name)
        .limit(limit)
        .all()
    )
```

- [ ] **Step 2: Also search aliases**

```python
def search_ingredients(self, query: str, limit: int = 50) -> list[IngredientORM]:
    from sqlalchemy import or_
    from src.storage.orm_models import IngredientAliasORM
    
    # Direct match on canonical_name or inci_name
    direct = (
        self._session.query(IngredientORM)
        .filter(or_(
            IngredientORM.canonical_name.ilike(f"%{query}%"),
            IngredientORM.inci_name.ilike(f"%{query}%"),
        ))
        .limit(limit)
        .all()
    )
    
    if len(direct) >= limit:
        return direct
    
    # Also check aliases
    direct_ids = {i.id for i in direct}
    alias_matches = (
        self._session.query(IngredientORM)
        .join(IngredientAliasORM)
        .filter(IngredientAliasORM.alias.ilike(f"%{query}%"))
        .filter(IngredientORM.id.notin_(direct_ids))
        .limit(limit - len(direct))
        .all()
    )
    
    return direct + alias_matches
```

- [ ] **Step 3: Commit**

```bash
git add src/storage/repository.py
git commit -m "feat: bilingual ingredient search (canonical + INCI + aliases)"
```

---

### Task 5: Seal Detection from Page Text

**Files:**
- Modify: `src/core/label_engine.py`

- [ ] **Step 1: Add full-text scanning method**

In `LabelEngine`, add method to scan arbitrary text (product page HTML text) for seal claims:

```python
def detect_seals_from_text(self, text: str) -> list[str]:
    """Scan text for seal/claim keywords. Returns list of detected seal names."""
    detected = []
    text_lower = text.lower()
    
    for seal in self._seals:
        seal_name = seal["name"]
        for kw in seal.get("keywords", []):
            if kw.lower() in text_lower:
                detected.append(seal_name)
                break
    
    return list(set(detected))
```

- [ ] **Step 2: Integrate into extraction pipeline**

In `src/pipeline/coverage_engine.py`, after extracting product data, call:

```python
# After extraction, scan page text for seals
if html_text:
    page_seals = label_engine.detect_seals_from_text(html_text)
    if page_seals:
        existing_labels = product.product_labels or {}
        existing_detected = existing_labels.get("detected", [])
        new_detected = list(set(existing_detected + page_seals))
        existing_labels["detected"] = new_detected
        product.product_labels = existing_labels
```

- [ ] **Step 3: Commit**

```bash
git add src/core/label_engine.py
git commit -m "feat: detect seals from full page text during scraping"
```

---

### Task 6: Enhanced Dashboard

**Files:**
- Modify: `frontend/src/pages/ops/OpsDashboard.tsx`

- [ ] **Step 1: Add coverage breakdown by field**

After the KPI grid, add a data completeness section:

```tsx
{/* Data Completeness */}
<div className={cardCls}>
  <h2 className="text-sm font-semibold text-ink mb-4">Completude dos Dados</h2>
  <div className="space-y-2">
    {[
      { label: "INCI", pct: kpis.inci_coverage, color: "emerald" },
      { label: "Categoria", pct: kpis.category_pct || 0, color: "blue" },
      { label: "Descrição", pct: kpis.description_pct || 0, color: "amber" },
      { label: "Imagem", pct: kpis.image_pct || 0, color: "purple" },
      { label: "Volume", pct: kpis.volume_pct || 0, color: "cyan" },
    ].map(({ label, pct, color }) => (
      <div key={label} className="flex items-center gap-3">
        <span className="text-xs text-ink-muted w-20">{label}</span>
        <div className="flex-1 h-2 rounded-full bg-cream-dark overflow-hidden">
          <div className={`h-full rounded-full bg-${color}-500`} style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-medium text-ink tabular-nums w-12 text-right">{pct}%</span>
      </div>
    ))}
  </div>
</div>
```

- [ ] **Step 2: Update dashboard API to return field coverage percentages**

In `src/api/routes/ops.py` dashboard endpoint, add:

```python
# Field coverage
hair_total = session.query(func.count(ProductORM.id)).filter(
    or_(ProductORM.product_category.is_(None), ProductORM.product_category != "non_hair")
).scalar() or 1

category_pct = round(session.query(func.count(ProductORM.id)).filter(
    ProductORM.product_category.isnot(None), ProductORM.product_category != "", ProductORM.product_category != "non_hair"
).scalar() / hair_total * 100, 1)

description_pct = round(session.query(func.count(ProductORM.id)).filter(
    ProductORM.description.isnot(None), ProductORM.description != ""
).scalar() / hair_total * 100, 1)

image_pct = round(session.query(func.count(ProductORM.id)).filter(
    ProductORM.image_url_main.isnot(None)
).scalar() / hair_total * 100, 1)

volume_pct = round(session.query(func.count(ProductORM.id)).filter(
    ProductORM.size_volume.isnot(None), ProductORM.size_volume != ""
).scalar() / hair_total * 100, 1)
```

Add to KPIs response: `"category_pct": category_pct, "description_pct": description_pct, "image_pct": image_pct, "volume_pct": volume_pct`

- [ ] **Step 3: Build and verify**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/ops.py frontend/src/pages/ops/OpsDashboard.tsx
git commit -m "feat: dashboard data completeness bars for all fields"
```

---

### Task 7: Product List Filters Enhancement

**Files:**
- Modify: `frontend/src/pages/ops/OpsProducts.tsx`
- Modify: `src/api/routes/ops.py:129-180`

- [ ] **Step 1: Add "sem INCI" / "sem descrição" / "sem categoria" filter pills**

In OpsProducts.tsx, add a new filter for data gaps:

```tsx
<select
  value={gapFilter}
  onChange={(e) => { setGapFilter(e.target.value); setPage(1); }}
  className={pillCls(!!gapFilter)}
>
  <option value="">Gaps ▾</option>
  <option value="sem_inci">Sem INCI</option>
  <option value="sem_descricao">Sem Descrição</option>
  <option value="sem_categoria">Sem Categoria</option>
  <option value="sem_preco">Sem Preço</option>
  <option value="sem_volume">Sem Volume</option>
</select>
```

- [ ] **Step 2: Add gap filter to backend**

In `ops_list_products`, add parameter:

```python
gap: str | None = None,  # sem_inci, sem_descricao, sem_categoria, sem_preco, sem_volume
```

Apply filter:
```python
if gap == "sem_inci":
    q = q.filter(ProductORM.verification_status != "verified_inci")
elif gap == "sem_descricao":
    q = q.filter(or_(ProductORM.description.is_(None), ProductORM.description == ""))
elif gap == "sem_categoria":
    q = q.filter(or_(ProductORM.product_category.is_(None), ProductORM.product_category == ""))
elif gap == "sem_preco":
    q = q.filter(ProductORM.price.is_(None))
elif gap == "sem_volume":
    q = q.filter(or_(ProductORM.size_volume.is_(None), ProductORM.size_volume == ""))
```

- [ ] **Step 3: Update frontend API call to include gap parameter**

In `ops-api.ts`, add `gap` to `opsListProducts` params.

- [ ] **Step 4: Build and commit**

```bash
cd frontend && npm run build
git add src/api/routes/ops.py frontend/src/pages/ops/OpsProducts.tsx frontend/src/lib/ops-api.ts
git commit -m "feat: gap filters — show products missing INCI, description, category, etc."
```

---

### Task 8: Quick-Fill Mode

**Files:**
- Create: `frontend/src/pages/ops/OpsQuickFill.tsx`
- Modify: `frontend/src/App.tsx` (add route)
- Modify: `frontend/src/components/ops/OpsLayout.tsx` (add nav)

- [ ] **Step 1: Create QuickFill page**

Single-product-at-a-time view focused on filling gaps. Shows one product with missing fields highlighted, "Salvar e Próximo" / "Pular" buttons.

```tsx
export default function OpsQuickFill() {
  // Fetches products with most gaps first (ordered by data_quality.pct ASC)
  // Shows product detail in simplified form (only empty fields highlighted)
  // "Salvar e Próximo" saves and loads next product
  // "Pular" loads next without saving
  // Counter: "3/50 preenchidos nesta sessão"
}
```

- [ ] **Step 2: Add route and nav link**

In App.tsx: `<Route path="quick-fill" element={<OpsQuickFill />} />`

In OpsLayout.tsx, add nav item with `Zap` icon from lucide-react.

- [ ] **Step 3: Build and commit**

```bash
cd frontend && npm run build
git add frontend/src/pages/ops/OpsQuickFill.tsx frontend/src/App.tsx frontend/src/components/ops/OpsLayout.tsx
git commit -m "feat: quick-fill mode — fill product gaps one at a time"
```

---

### Task 9: Deploy + Verify

- [ ] **Step 1: Final build**

```bash
cd frontend && npm run build
```

- [ ] **Step 2: Deploy to Railway**

```bash
railway up --detach
```

- [ ] **Step 3: Verify in production**

- Open https://haira-app-production-deb8.up.railway.app/ops
- Test: edit a product → should see validation errors if name too short
- Test: upload photo → should extract INCI
- Test: dashboard → should show completeness bars
- Test: products → gap filters should work
- Test: quick-fill → should cycle through products with gaps

- [ ] **Step 4: Final commit**

```bash
git commit -m "deploy: HAIRA perfeito — all features integrated"
```

---

## Verification Checklist

- [ ] Validation blocks saving products with empty names or invalid categories
- [ ] Validation warnings shown inline (amber) without blocking save
- [ ] Evidence records created when INCI is manually edited
- [ ] Ingredient search finds by Portuguese AND English/INCI names
- [ ] Dashboard shows completeness bars for all fields
- [ ] Gap filters work in product list
- [ ] Quick-fill mode cycles through products with most gaps
- [ ] Photo upload extracts INCI and allows applying to product
- [ ] Build passes with no TS errors
- [ ] Deploy succeeds on Railway
