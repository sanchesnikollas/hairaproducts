import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";

interface DualValidationItem {
  id: string;
  product_id: string;
  field_name: string;
  status: string;
  reviewer_notes: string | null;
  created_at: string | null;
  product_name: string | null;
  brand_slug: string | null;
  comparison: {
    pass_1_value: string | null;
    pass_2_value: string | null;
    resolution: string;
  } | null;
}

const FIELD_LABELS: Record<string, string> = {
  product_name: "Nome",
  price: "Preço",
  description: "Descrição",
  composition: "Composição",
  care_usage: "Modo de uso",
  inci_ingredients: "INCI",
  image_url_main: "Imagem",
};

async function fetchDualValidationQueue(brand?: string): Promise<DualValidationItem[]> {
  const qs = new URLSearchParams();
  qs.set("status", "pending");
  if (brand) qs.set("brand_slug", brand);
  const res = await fetch(`/api/review-queue?${qs}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function resolveItem(itemId: string, status: string, notes?: string): Promise<void> {
  const res = await fetch(`/api/review-queue/${itemId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, reviewer_notes: notes }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

function truncate(s: string | null, max: number): string {
  if (!s) return "—";
  return s.length > max ? s.substring(0, max) + "…" : s;
}

export default function OpsDualValidation() {
  const [brand, setBrand] = useState("");
  const [processing, setProcessing] = useState<string | null>(null);

  const fetcher = useCallback(() => fetchDualValidationQueue(brand || undefined), [brand]);
  const { data, loading, error, refetch } = useAPI<DualValidationItem[]>(fetcher, [brand]);

  const handleResolve = async (itemId: string, status: string) => {
    setProcessing(itemId);
    try {
      await resolveItem(itemId, status);
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao resolver");
    } finally {
      setProcessing(null);
    }
  };

  // Group items by product
  const grouped = (data || []).reduce<Record<string, DualValidationItem[]>>((acc, item) => {
    const key = item.product_id;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold text-ink">Dupla Verificação</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Divergências entre extração determinística (Pass 1) e LLM grounded (Pass 2). Resolva escolhendo qual valor é correto.
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Filtrar por brand..."
          value={brand}
          onChange={(e) => setBrand(e.target.value)}
          className="w-48 rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
        />
        {data && (
          <span className="text-sm text-ink-muted">
            {data.length} divergências em {Object.keys(grouped).length} produto(s)
          </span>
        )}
      </div>

      {loading && <p className="text-ink-muted">Carregando...</p>}
      {error && <p className="text-coral">Erro: {error}</p>}

      {data && data.length === 0 && (
        <div className="rounded-xl border border-cream-dark bg-cream/30 p-8 text-center">
          <p className="text-ink-muted">Nenhuma divergência pendente.</p>
          <p className="mt-2 text-xs text-ink-muted">
            Rode <code className="rounded bg-cream px-1.5 py-0.5">haira validate --brand &lt;slug&gt;</code> para gerar verificações.
          </p>
        </div>
      )}

      {/* Items grouped by product */}
      <div className="space-y-4">
        {Object.entries(grouped).map(([productId, items]) => (
          <div key={productId} className="rounded-xl border border-cream-dark bg-white p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Link
                  to={`/ops/products/${productId}`}
                  className="font-medium text-ink hover:underline"
                >
                  {items[0].product_name}
                </Link>
                <p className="text-xs text-ink-muted">
                  {items[0].brand_slug} · {items.length} campo(s) divergente(s)
                </p>
              </div>
            </div>

            <div className="space-y-2">
              {items.map((item) => (
                <div key={item.id} className="rounded-lg border border-amber-200 bg-amber-50/50 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-amber-800">
                      {FIELD_LABELS[item.field_name] || item.field_name}
                    </span>
                    <span className="text-[10px] text-ink-muted">
                      {item.created_at ? new Date(item.created_at).toLocaleString("pt-BR") : ""}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="rounded border border-cream-dark bg-white p-2">
                      <div className="mb-1 text-[10px] font-medium uppercase text-ink-muted">
                        Pass 1 (deterministic)
                      </div>
                      <div className="break-words text-ink">
                        {truncate(item.comparison?.pass_1_value ?? null, 200)}
                      </div>
                    </div>
                    <div className="rounded border border-cream-dark bg-white p-2">
                      <div className="mb-1 text-[10px] font-medium uppercase text-ink-muted">
                        Pass 2 (LLM grounded)
                      </div>
                      <div className="break-words text-ink">
                        {truncate(item.comparison?.pass_2_value ?? null, 200)}
                      </div>
                    </div>
                  </div>

                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => handleResolve(item.id, "approved_pass_1")}
                      disabled={processing === item.id}
                      className="rounded bg-cream px-2.5 py-1 text-[10px] font-medium text-ink hover:bg-cream-dark disabled:opacity-50"
                    >
                      Manter Pass 1
                    </button>
                    <button
                      onClick={() => handleResolve(item.id, "approved_pass_2")}
                      disabled={processing === item.id}
                      className="rounded bg-emerald-100 px-2.5 py-1 text-[10px] font-medium text-emerald-800 hover:bg-emerald-200 disabled:opacity-50"
                    >
                      Aceitar Pass 2
                    </button>
                    <button
                      onClick={() => handleResolve(item.id, "rejected")}
                      disabled={processing === item.id}
                      className="rounded bg-red-100 px-2.5 py-1 text-[10px] font-medium text-red-800 hover:bg-red-200 disabled:opacity-50"
                    >
                      Rejeitar ambos
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
