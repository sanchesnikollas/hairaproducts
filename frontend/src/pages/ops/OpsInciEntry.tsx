import { useState, useCallback } from "react";
import { useAPI } from "../../hooks/useAPI";
import { opsGetInciSummary, opsListProducts, opsUpdateProduct } from "../../lib/ops-api";
import type { InciSummaryBrand } from "../../lib/ops-api";

const PER_PAGE = 20;

function parseInci(raw: string): string[] {
  return raw
    .split(/[,;]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function OpsInciEntry() {
  const [selectedBrand, setSelectedBrand] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expandedProduct, setExpandedProduct] = useState<string | null>(null);
  const [inciText, setInciText] = useState("");
  const [saving, setSaving] = useState(false);

  // Brand-level INCI summary
  const summaryFetcher = useCallback(() => opsGetInciSummary(), []);
  const { data: summary, loading: summaryLoading, error: summaryError, refetch: refetchSummary } = useAPI(summaryFetcher, []);

  // Products for selected brand
  const productsFetcher = useCallback(
    () =>
      selectedBrand
        ? opsListProducts({ brand: selectedBrand, verification_status: "catalog_only", page, per_page: PER_PAGE })
        : Promise.resolve({ items: [], total: 0, page: 1, per_page: PER_PAGE }),
    [selectedBrand, page],
  );
  const { data: products, loading: productsLoading, refetch: refetchProducts } = useAPI(productsFetcher, [selectedBrand, page]);

  const handleSelectBrand = (slug: string) => {
    setSelectedBrand(slug);
    setPage(1);
    setExpandedProduct(null);
    setInciText("");
  };

  const handleExpand = (productId: string) => {
    if (expandedProduct === productId) {
      setExpandedProduct(null);
      setInciText("");
    } else {
      setExpandedProduct(productId);
      setInciText("");
    }
  };

  const handleSaveInci = async (productId: string) => {
    const ingredients = parseInci(inciText);
    if (ingredients.length === 0) return;

    setSaving(true);
    try {
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

  const sortedBrands = summary
    ? [...summary.brands].filter((b) => b.pending > 0).sort((a, b) => b.pending - a.pending)
    : [];

  const ingredientCount = inciText.trim() ? parseInci(inciText).length : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-ink">Entrada INCI Manual</h1>
          {summary && (
            <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
              {summary.total_pending} pendentes
            </span>
          )}
        </div>
        <p className="mt-1 text-sm text-ink-muted">
          Selecione uma marca e insira a composição INCI a partir da embalagem do produto.
        </p>
      </div>

      {/* Loading / Error */}
      {summaryLoading && <p className="text-ink-muted">Carregando marcas...</p>}
      {summaryError && <p className="text-coral">Erro: {summaryError}</p>}

      {/* Brand selector grid */}
      {summary && (
        <div>
          <h2 className="text-sm font-semibold text-ink mb-3">Marcas</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
            {sortedBrands.map((brand: InciSummaryBrand) => (
              <button
                key={brand.brand_slug}
                onClick={() => handleSelectBrand(brand.brand_slug)}
                className={`rounded-xl border border-cream-dark p-3 text-left transition-colors ${
                  selectedBrand === brand.brand_slug
                    ? "bg-ink text-white border-ink"
                    : "bg-white hover:bg-cream"
                }`}
              >
                <p className={`text-sm font-medium truncate ${selectedBrand === brand.brand_slug ? "text-white" : "text-ink"}`}>
                  {brand.brand_slug}
                </p>
                <div className="mt-1 flex items-center justify-between">
                  <span className={`text-xs ${selectedBrand === brand.brand_slug ? "text-white/70" : "text-ink-muted"}`}>
                    {brand.pending} pendente{brand.pending !== 1 ? "s" : ""}
                  </span>
                  <span className={`text-xs font-medium ${
                    selectedBrand === brand.brand_slug
                      ? "text-white/70"
                      : brand.pct >= 80
                        ? "text-emerald-600"
                        : brand.pct >= 50
                          ? "text-amber-600"
                          : "text-red-500"
                  }`}>
                    {brand.pct}% INCI
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Product queue */}
      {selectedBrand && (
        <div>
          <h2 className="text-sm font-semibold text-ink mb-3">
            Produtos catalog_only — {selectedBrand}
            {products && (
              <span className="ml-2 text-xs font-normal text-ink-muted">({products.total} produto{products.total !== 1 ? "s" : ""})</span>
            )}
          </h2>

          {productsLoading && <p className="text-ink-muted text-sm">Carregando produtos...</p>}

          {products && products.items.length === 0 && !productsLoading && (
            <div className="rounded-xl border border-cream-dark bg-white p-6 text-center">
              <p className="text-sm text-ink-muted">Nenhum produto catalog_only para esta marca.</p>
            </div>
          )}

          {products && products.items.length > 0 && (
            <div className="space-y-2">
              {products.items.map((p) => (
                <div key={p.id} className="rounded-xl border border-cream-dark bg-white">
                  {/* Product row */}
                  <button
                    onClick={() => handleExpand(p.id)}
                    className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-cream/50 transition-colors rounded-xl"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink truncate">{p.product_name}</p>
                      <p className="text-xs text-ink-muted">{p.brand_slug}</p>
                    </div>
                    <span className="ml-3 text-xs text-ink-muted">
                      {expandedProduct === p.id ? "▲" : "▼"}
                    </span>
                  </button>

                  {/* Expanded INCI entry */}
                  {expandedProduct === p.id && (
                    <div className="border-t border-cream-dark px-4 py-4 space-y-3">
                      <label className="block text-xs text-ink-muted">
                        Cole a lista de ingredientes (INCI) separados por virgula ou ponto-e-virgula:
                      </label>
                      <textarea
                        value={inciText}
                        onChange={(e) => setInciText(e.target.value)}
                        rows={4}
                        placeholder="Aqua, Cetearyl Alcohol, Behentrimonium Chloride, ..."
                        className="w-full rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
                      />
                      {inciText.trim() && (
                        <p className="text-xs text-ink-muted">
                          {ingredientCount} ingrediente{ingredientCount !== 1 ? "s" : ""} detectado{ingredientCount !== 1 ? "s" : ""}
                        </p>
                      )}
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => { setExpandedProduct(null); setInciText(""); }}
                          className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream"
                        >
                          Cancelar
                        </button>
                        <button
                          onClick={() => handleSaveInci(p.id)}
                          disabled={saving || ingredientCount === 0}
                          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                        >
                          {saving ? "Salvando..." : "Salvar INCI"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Págination */}
              {products.total > PER_PAGE && (
                <div className="flex items-center justify-between pt-2 text-sm text-ink-muted">
                  <span>{products.total} produtos total</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50"
                    >
                      Anterior
                    </button>
                    <span className="flex items-center px-2">Página {page}</span>
                    <button
                      onClick={() => setPage((p) => p + 1)}
                      disabled={products.items.length < products.per_page}
                      className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50"
                    >
                      Próxima
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
