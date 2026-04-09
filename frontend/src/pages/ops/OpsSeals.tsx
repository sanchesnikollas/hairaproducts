import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";

const SEAL_LABELS: Record<string, { label: string; emoji: string; description: string }> = {
  sulfate_free: { label: "Sem Sulfato", emoji: "🧴", description: "Não contém sulfatos agressivos" },
  silicone_free: { label: "Sem Silicone", emoji: "💧", description: "Livre de silicones insolúveis" },
  paraben_free: { label: "Sem Parabeno", emoji: "🛡️", description: "Livre de parabenos" },
  petrolatum_free: { label: "Sem Petrolato", emoji: "🌿", description: "Livre de derivados de petróleo" },
  dye_free: { label: "Sem Corante", emoji: "🎨", description: "Sem corantes artificiais" },
  low_poo: { label: "Low Poo", emoji: "🫧", description: "Sulfatos leves permitidos" },
  no_poo: { label: "No Poo", emoji: "🚫", description: "Zero sulfatos" },
  vegan: { label: "Vegano", emoji: "🌱", description: "Sem ingredientes de origem animal" },
  cruelty_free: { label: "Cruelty Free", emoji: "🐰", description: "Não testado em animais" },
  natural: { label: "Natural", emoji: "🍃", description: "Ingredientes naturais" },
  organic: { label: "Orgânico", emoji: "🌾", description: "Ingredientes orgânicos certificados" },
  dermatologically_tested: { label: "Dermatologicamente Testado", emoji: "✅", description: "Aprovado em testes dermatológicos" },
  uv_protection: { label: "Proteção UV", emoji: "☀️", description: "Proteção contra raios UV" },
  thermal_protection: { label: "Proteção Térmica", emoji: "🔥", description: "Protege do calor" },
  fragrance_free: { label: "Sem Fragrância", emoji: "👃", description: "Livre de fragrâncias artificiais" },
  ophthalmologically_tested: { label: "Oftalmologicamente Testado", emoji: "👁️", description: "Seguro para região dos olhos" },
};

interface SealSummary { name: string; count: number; }
interface SealProduct { id: string; product_name: string; brand_slug: string; image_url_main: string | null; product_category: string | null; verification_status: string; }

async function fetchSeals(): Promise<{ seals: SealSummary[]; total_products_with_seals: number }> {
  const token = localStorage.getItem("haira_token");
  const resp = await fetch("/api/ops/seals", { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

async function fetchSealProducts(seal: string, page: number): Promise<{ seal: string; total: number; page: number; per_page: number; items: SealProduct[] }> {
  const token = localStorage.getItem("haira_token");
  const resp = await fetch(`/api/ops/seals/${seal}/products?page=${page}&per_page=20`, { headers: { Authorization: `Bearer ${token}` } });
  if (!resp.ok) throw new Error(`API error: ${resp.status}`);
  return resp.json();
}

export default function OpsSeals() {
  const [selectedSeal, setSelectedSeal] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const { data, loading, error } = useAPI(fetchSeals, []);

  const productsFetcher = useCallback(
    () => selectedSeal ? fetchSealProducts(selectedSeal, page) : Promise.resolve(null),
    [selectedSeal, page],
  );
  const { data: productsData, loading: productsLoading } = useAPI(productsFetcher, [selectedSeal, page]);

  const getSealInfo = (name: string) => SEAL_LABELS[name] || { label: name.replace(/_/g, " "), emoji: "🏷️", description: "" };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Selos de Qualidade</h1>
        <p className="mt-1 text-sm text-ink-muted">
          {data ? `${data.total_products_with_seals.toLocaleString()} produtos com selos detectados` : "Carregando..."}
        </p>
      </div>

      {loading && <p className="text-ink-muted">Carregando selos...</p>}
      {error && <p className="text-coral">Erro: {error}</p>}

      {/* Seal Grid */}
      {data && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {data.seals.map((seal) => {
            const info = getSealInfo(seal.name);
            const isSelected = selectedSeal === seal.name;
            return (
              <button
                key={seal.name}
                onClick={() => { setSelectedSeal(isSelected ? null : seal.name); setPage(1); }}
                className={`rounded-xl border p-4 text-left transition-all ${
                  isSelected
                    ? "border-ink bg-ink text-white shadow-lg"
                    : "border-cream-dark bg-white hover:border-ink/30 hover:shadow-sm"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xl">{info.emoji}</span>
                  <span className={`text-lg font-semibold tabular-nums ${isSelected ? "text-white" : "text-ink"}`}>
                    {seal.count.toLocaleString()}
                  </span>
                </div>
                <p className={`mt-2 text-sm font-medium ${isSelected ? "text-white" : "text-ink"}`}>
                  {info.label}
                </p>
                <p className={`mt-0.5 text-[10px] ${isSelected ? "text-white/70" : "text-ink-muted"}`}>
                  {info.description}
                </p>
              </button>
            );
          })}
        </div>
      )}

      {/* Selected Seal Products */}
      {selectedSeal && (
        <div className="rounded-xl border border-cream-dark bg-white">
          <div className="border-b border-cream-dark px-5 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-lg">{getSealInfo(selectedSeal).emoji}</span>
              <h2 className="text-sm font-semibold text-ink">{getSealInfo(selectedSeal).label}</h2>
              {productsData && (
                <span className="text-xs text-ink-muted">{productsData.total} produtos</span>
              )}
            </div>
            <button onClick={() => setSelectedSeal(null)} className="text-xs text-ink-muted hover:text-ink">
              Fechar ×
            </button>
          </div>

          {productsLoading && <p className="p-5 text-ink-muted text-sm">Carregando produtos...</p>}

          {productsData && productsData.items.length > 0 && (
            <>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-cream-dark text-left text-[10px] text-ink-muted uppercase tracking-wider">
                    <th className="w-10 px-1 py-3"></th>
                    <th className="px-3 py-3">Produto</th>
                    <th className="px-3 py-3 w-28">Marca</th>
                    <th className="px-3 py-3 w-24">Categoria</th>
                    <th className="px-3 py-3 w-24">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {productsData.items.map((p) => (
                    <tr key={p.id} className="border-b border-cream-dark/50 hover:bg-cream/50 transition-colors">
                      <td className="px-1 py-2">
                        {p.image_url_main ? (
                          <img src={p.image_url_main} alt="" className="h-8 w-8 rounded border border-cream-dark object-cover" />
                        ) : (
                          <div className="h-8 w-8 rounded border border-cream-dark bg-cream-dark/30" />
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <Link to={`/ops/products/${p.id}`} className="font-medium text-ink hover:underline">
                          {p.product_name}
                        </Link>
                      </td>
                      <td className="px-3 py-2 text-xs text-ink-muted">{p.brand_slug}</td>
                      <td className="px-3 py-2 text-xs text-ink-muted">{p.product_category || "—"}</td>
                      <td className="px-3 py-2">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          p.verification_status === "verified_inci" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {p.verification_status === "verified_inci" ? "verificado" : "catalog"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {productsData.total > 20 && (
                <div className="flex items-center justify-between px-5 py-3 text-sm text-ink-muted border-t border-cream-dark">
                  <span>{productsData.total} produtos</span>
                  <div className="flex gap-2">
                    <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                      Anterior
                    </button>
                    <span className="flex items-center px-2 tabular-nums">Página {page}</span>
                    <button onClick={() => setPage((p) => p + 1)} disabled={productsData.items.length < 20} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                      Próxima
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {productsData && productsData.items.length === 0 && (
            <p className="p-5 text-sm text-ink-muted">Nenhum produto encontrado com este selo.</p>
          )}
        </div>
      )}
    </div>
  );
}
