import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { getReviewQueue, startReview, resolveReview } from "../../lib/ops-api";
import type { ReviewQueueResponse, ReviewQueueItem as QueueItem } from "../../types/ops";

export default function OpsReview() {
  const [brand, setBrand] = useState("");
  const [page, setPage] = useState(1);
  const [activeItem, setActiveItem] = useState<QueueItem | null>(null);
  const [notes, setNotes] = useState("");
  const [processing, setProcessing] = useState(false);

  const fetcher = useCallback(
    () => getReviewQueue({ brand: brand || undefined, page }),
    [brand, page],
  );

  const { data, loading, error, refetch } = useAPI<ReviewQueueResponse>(fetcher, [brand, page]);

  const handleStart = async (item: QueueItem) => {
    try {
      await startReview(item.id);
      setActiveItem(item);
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao iniciar revisao");
    }
  };

  const handleResolve = async (decision: string) => {
    if (!activeItem) return;
    setProcessing(true);
    try {
      await resolveReview(activeItem.id, decision, notes || undefined);
      setActiveItem(null);
      setNotes("");
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao resolver");
    } finally {
      setProcessing(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-ink">Fila de Revisao</h1>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Filtrar por brand..."
          value={brand}
          onChange={(e) => { setBrand(e.target.value); setPage(1); }}
          className="w-48 rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
        />
        {data && (
          <span className="text-sm text-ink-muted">{data.total} itens na fila</span>
        )}
      </div>

      {loading && <p className="text-ink-muted">Carregando...</p>}
      {error && <p className="text-coral">Erro: {error}</p>}

      {/* Active review panel */}
      {activeItem && (
        <div className="rounded-xl border-2 border-blue-200 bg-blue-50 p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-sm font-semibold text-blue-900">Revisando</h2>
              <Link to={`/ops/products/${activeItem.id}`} className="text-lg font-medium text-ink hover:underline">
                {activeItem.product_name}
              </Link>
              <p className="text-sm text-ink-muted">{activeItem.brand_slug} · Confianca: {activeItem.confidence}%</p>
            </div>
            <span className="rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-700">Em revisao</span>
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Notas (opcional)</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              className="w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm outline-none focus:border-blue-400"
              placeholder="Observacoes sobre a revisao..."
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleResolve("approve")}
              disabled={processing}
              className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              Aprovar
            </button>
            <button
              onClick={() => handleResolve("correct")}
              disabled={processing}
              className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
            >
              Corrigir
            </button>
            <button
              onClick={() => handleResolve("reject")}
              disabled={processing}
              className="rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:opacity-50"
            >
              Rejeitar
            </button>
            <button
              onClick={() => { setActiveItem(null); setNotes(""); }}
              className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream"
            >
              Cancelar
            </button>
          </div>
        </div>
      )}

      {/* Queue list */}
      {data && (
        <>
          <div className="space-y-2">
            {data.items.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-xl border border-cream-dark bg-white px-5 py-3 hover:border-ink/20 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <Link to={`/ops/products/${item.id}`} className="font-medium text-ink hover:underline">
                    {item.product_name}
                  </Link>
                  <div className="mt-0.5 flex items-center gap-2 text-xs text-ink-muted">
                    <span>{item.brand_slug}</span>
                    <span>·</span>
                    <span className={item.confidence < 30 ? "text-red-500 font-medium" : ""}>{item.confidence}%</span>
                    {item.status_editorial && (
                      <>
                        <span>·</span>
                        <span>{item.status_editorial}</span>
                      </>
                    )}
                    {item.assigned_to && (
                      <>
                        <span>·</span>
                        <span className="text-blue-600">Atribuido</span>
                      </>
                    )}
                  </div>
                </div>
                {!activeItem && (
                  <button
                    onClick={() => handleStart(item)}
                    className="ml-4 rounded-lg bg-ink px-4 py-1.5 text-xs font-medium text-white hover:opacity-90"
                  >
                    Revisar
                  </button>
                )}
              </div>
            ))}
            {data.items.length === 0 && (
              <p className="py-8 text-center text-ink-muted">Nenhum item na fila de revisao</p>
            )}
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span>{data.total} itens total</span>
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
                disabled={data.items.length < data.per_page}
                className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50"
              >
                Proxima
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
