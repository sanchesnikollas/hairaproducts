import { useState, useCallback, useEffect } from "react";
import { useAPI } from "../../hooks/useAPI";
import { opsListProducts, opsUpdateProduct } from "../../lib/ops-api";
import CategorySelect from "../../components/ops/CategorySelect";

export default function OpsQuickFill() {
  const [page, setPage] = useState(1);
  const [filled, setFilled] = useState(0);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const fetcher = useCallback(
    () => opsListProducts({ gap: "sem_inci", page, per_page: 1 }),
    [page],
  );
  const { data, loading } = useAPI(fetcher, [page]);
  const product = data?.items?.[0];

  useEffect(() => {
    if (product) {
      setForm({
        description: "",
        product_category: "",
        size_volume: "",
      });
    }
  }, [product]);

  const handleSave = async () => {
    if (!product) return;
    setSaving(true);
    try {
      const updates: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(form)) {
        if (val.trim()) updates[key] = val.trim();
      }
      if (Object.keys(updates).length > 0) {
        await opsUpdateProduct(product.id, updates);
      }
      setFilled((f) => f + 1);
      setPage((p) => p + 1);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  const handleSkip = () => {
    setPage((p) => p + 1);
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink">Preencher Dados</h1>
        <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
          {filled} preenchidos nesta sessao
        </span>
      </div>

      {loading && <p className="text-ink-muted">Carregando...</p>}

      {!loading && !product && (
        <div className="rounded-xl border border-cream-dark bg-white p-8 text-center">
          <p className="text-ink-muted">Nenhum produto com gaps encontrado. Bom trabalho!</p>
        </div>
      )}

      {product && (
        <div className="rounded-xl border border-cream-dark bg-white p-6 space-y-5">
          {/* Product header */}
          <div className="flex items-start gap-4">
            {product.image_url_main ? (
              <img
                src={product.image_url_main}
                alt=""
                className="h-20 w-20 rounded-lg border border-cream-dark object-cover flex-shrink-0"
              />
            ) : (
              <div className="h-20 w-20 rounded-lg border border-cream-dark bg-cream-dark/30 flex-shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold text-ink">{product.product_name}</h2>
              <p className="text-sm text-ink-muted">{product.brand_slug}</p>
              <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${
                product.verification_status === "verified_inci"
                  ? "bg-emerald-100 text-emerald-700"
                  : product.verification_status === "quarantined"
                  ? "bg-red-100 text-red-700"
                  : "bg-amber-100 text-amber-700"
              }`}>
                {product.verification_status}
              </span>
            </div>
          </div>

          {/* Editable fields */}
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-ink-muted">Descricao</label>
              <textarea
                rows={3}
                value={form.description || ""}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Descricao do produto..."
                className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink transition-colors"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-muted">Categoria</label>
                <CategorySelect
                  value={form.product_category || ""}
                  onChange={(v) => setForm({ ...form, product_category: v })}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-ink-muted">Volume</label>
                <input
                  type="text"
                  value={form.size_volume || ""}
                  onChange={(e) => setForm({ ...form, size_volume: e.target.value })}
                  placeholder="ex: 300ml"
                  className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink transition-colors"
                />
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between border-t border-cream-dark pt-4">
            <button
              onClick={handleSkip}
              className="rounded-lg border border-cream-dark px-4 py-2 text-sm text-ink-muted hover:bg-cream transition-colors"
            >
              Pular
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-ink px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {saving ? "Salvando..." : "Salvar e Proximo"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
