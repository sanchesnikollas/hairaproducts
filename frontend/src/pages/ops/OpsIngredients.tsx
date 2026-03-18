import { useState, useCallback } from "react";
import { useAPI } from "../../hooks/useAPI";
import { fetchIngredients } from "../../lib/api";
import { getIngredientGaps, opsUpdateIngredient } from "../../lib/ops-api";
import type { IngredientSummary } from "../../types/api";
import type { IngredientGaps } from "../../types/ops";

type Tab = "browse" | "gaps";

export default function OpsIngredients() {
  const [activeTab, setActiveTab] = useState<Tab>("browse");
  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editCategory, setEditCategory] = useState("");

  const ingredientFetcher = useCallback(
    () => fetchIngredients(search || undefined),
    [search],
  );
  const { data: ingredients, loading: loadingIng, refetch: refetchIng } = useAPI<IngredientSummary[]>(ingredientFetcher, [search]);
  const { data: gaps, loading: loadingGaps, refetch: refetchGaps } = useAPI<IngredientGaps>(() => getIngredientGaps(), []);

  const handleSaveCategory = async (id: string) => {
    try {
      await opsUpdateIngredient(id, { category: editCategory });
      setEditingId(null);
      setEditCategory("");
      refetchIng();
      refetchGaps();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar");
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "browse", label: "Navegar" },
    { key: "gaps", label: "Gaps" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-ink">Ingredientes</h1>

      <div className="flex gap-1 border-b border-cream-dark">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm transition-colors ${
              activeTab === tab.key
                ? "border-b-2 border-ink font-medium text-ink"
                : "text-ink-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "browse" && (
        <div className="space-y-4">
          <input
            type="text"
            placeholder="Buscar ingrediente..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-64 rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
          />

          {loadingIng && <p className="text-ink-muted">Carregando...</p>}

          {ingredients && (
            <div className="overflow-x-auto rounded-xl border border-cream-dark bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark text-left text-xs text-ink-muted uppercase tracking-wider">
                    <th className="px-4 py-3">Nome Canonico</th>
                    <th className="px-4 py-3">INCI</th>
                    <th className="px-4 py-3">Categoria</th>
                    <th className="px-4 py-3">Produtos</th>
                    <th className="px-4 py-3">Acoes</th>
                  </tr>
                </thead>
                <tbody>
                  {ingredients.map((ing) => (
                    <tr key={ing.id} className="border-b border-cream-dark/50 hover:bg-cream/50">
                      <td className="px-4 py-3 font-medium text-ink">{ing.canonical_name}</td>
                      <td className="px-4 py-3 text-ink-muted">{ing.inci_name || "-"}</td>
                      <td className="px-4 py-3">
                        {editingId === ing.id ? (
                          <div className="flex items-center gap-2">
                            <input
                              type="text"
                              value={editCategory}
                              onChange={(e) => setEditCategory(e.target.value)}
                              className="w-32 rounded border border-cream-dark px-2 py-1 text-xs"
                              placeholder="Categoria"
                            />
                            <button onClick={() => handleSaveCategory(ing.id)} className="text-xs text-emerald-600 hover:underline">Salvar</button>
                            <button onClick={() => setEditingId(null)} className="text-xs text-ink-muted hover:underline">X</button>
                          </div>
                        ) : (
                          <span className={ing.category ? "text-ink" : "text-ink-muted italic"}>
                            {ing.category || "sem categoria"}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-ink-muted">{ing.product_count}</td>
                      <td className="px-4 py-3">
                        <button
                          onClick={() => { setEditingId(ing.id); setEditCategory(ing.category || ""); }}
                          className="text-xs text-ink-muted hover:text-ink hover:underline"
                        >
                          Editar
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === "gaps" && (
        <div className="space-y-6">
          {loadingGaps && <p className="text-ink-muted">Carregando gaps...</p>}

          {gaps && (
            <>
              <div className="rounded-xl border border-cream-dark bg-white p-5">
                <h2 className="mb-3 text-sm font-semibold text-ink">Sem Categoria ({gaps.uncategorized.length})</h2>
                {gaps.uncategorized.length === 0 ? (
                  <p className="text-xs text-ink-muted">Todos ingredientes categorizados</p>
                ) : (
                  <div className="space-y-1 max-h-80 overflow-y-auto">
                    {gaps.uncategorized.map((ing) => (
                      <div key={ing.id} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-cream">
                        <div>
                          <span className="font-medium text-ink">{ing.canonical_name}</span>
                          {ing.inci_name && <span className="ml-2 text-xs text-ink-muted">({ing.inci_name})</span>}
                        </div>
                        <button
                          onClick={() => { setActiveTab("browse"); setSearch(ing.canonical_name); }}
                          className="text-xs text-ink-muted hover:text-ink hover:underline"
                        >
                          Categorizar
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-xl border border-cream-dark bg-white p-5">
                <h2 className="mb-3 text-sm font-semibold text-ink">Raw Names Orfaos ({gaps.orphan_raw_names.length})</h2>
                {gaps.orphan_raw_names.length === 0 ? (
                  <p className="text-xs text-ink-muted">Sem orfaos</p>
                ) : (
                  <div className="space-y-1 max-h-80 overflow-y-auto">
                    {gaps.orphan_raw_names.map((o, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-cream">
                        <span className="text-ink">{o.raw_name}</span>
                        <span className="text-xs text-ink-muted">{o.product_count} produtos</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
