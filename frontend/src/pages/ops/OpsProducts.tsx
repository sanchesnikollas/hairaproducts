import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsListProducts, opsBatchUpdate } from "../../lib/ops-api";
import { useAuth } from "../../lib/auth";

export default function OpsProducts() {
  const { isAdmin } = useAuth();
  const [brand, setBrand] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchAction, setBatchAction] = useState("");

  const fetcher = useCallback(
    () => opsListProducts({ brand: brand || undefined, status_editorial: statusFilter || undefined, search: search || undefined, page }),
    [brand, statusFilter, search, page],
  );

  const { data, loading, error, refetch } = useAPI(fetcher, [brand, statusFilter, search, page]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!data) return;
    if (selected.size === data.items.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(data.items.map((p) => p.id)));
    }
  };

  const handleBatchAction = async () => {
    if (!batchAction || selected.size === 0) return;
    try {
      await opsBatchUpdate(Array.from(selected), { status_editorial: batchAction });
      setSelected(new Set());
      setBatchAction("");
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao atualizar");
    }
  };

  const statusBadge = (status: string | null) => {
    const colors: Record<string, string> = {
      pendente: "bg-amber-100 text-amber-700",
      em_revisao: "bg-blue-100 text-blue-700",
      aprovado: "bg-emerald-100 text-emerald-700",
      corrigido: "bg-teal-100 text-teal-700",
      rejeitado: "bg-red-100 text-red-700",
    };
    if (!status) return null;
    return (
      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] || "bg-gray-100 text-gray-600"}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-ink">Produtos</h1>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <input
          type="text"
          placeholder="Buscar por nome..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
        />
        <input
          type="text"
          placeholder="Brand slug"
          value={brand}
          onChange={(e) => { setBrand(e.target.value); setPage(1); }}
          className="w-36 rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink"
        />
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className="rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none"
        >
          <option value="">Todos status</option>
          <option value="pendente">Pendente</option>
          <option value="em_revisao">Em Revisao</option>
          <option value="aprovado">Aprovado</option>
          <option value="corrigido">Corrigido</option>
          <option value="rejeitado">Rejeitado</option>
        </select>
      </div>

      {/* Batch actions */}
      {isAdmin && selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg bg-blue-50 px-4 py-2">
          <span className="text-sm text-blue-700">{selected.size} selecionados</span>
          <select
            value={batchAction}
            onChange={(e) => setBatchAction(e.target.value)}
            className="rounded border border-blue-200 bg-white px-2 py-1 text-sm"
          >
            <option value="">Acao em lote...</option>
            <option value="aprovado">Aprovar</option>
            <option value="rejeitado">Rejeitar</option>
            <option value="pendente">Voltar p/ Pendente</option>
          </select>
          <button
            onClick={handleBatchAction}
            disabled={!batchAction}
            className="rounded-lg bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Aplicar
          </button>
        </div>
      )}

      {/* Loading / Error */}
      {loading && <p className="text-ink-muted">Carregando...</p>}
      {error && <p className="text-coral">Erro: {error}</p>}

      {/* Table */}
      {data && (
        <>
          <div className="overflow-x-auto rounded-xl border border-cream-dark bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-dark text-left text-xs text-ink-muted uppercase tracking-wider">
                  {isAdmin && (
                    <th className="px-4 py-3">
                      <input type="checkbox" onChange={toggleAll} checked={selected.size === data.items.length && data.items.length > 0} />
                    </th>
                  )}
                  <th className="px-4 py-3">Produto</th>
                  <th className="px-4 py-3">Brand</th>
                  <th className="px-4 py-3">Status Editorial</th>
                  <th className="px-4 py-3">Verificacao</th>
                  <th className="px-4 py-3">Confianca</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="border-b border-cream-dark/50 hover:bg-cream/50 transition-colors">
                    {isAdmin && (
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} />
                      </td>
                    )}
                    <td className="px-4 py-3">
                      <Link to={`/ops/products/${p.id}`} className="font-medium text-ink hover:underline">
                        {p.product_name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-ink-muted">{p.brand_slug}</td>
                    <td className="px-4 py-3">{statusBadge(p.status_editorial)}</td>
                    <td className="px-4 py-3 text-xs text-ink-muted">{p.verification_status}</td>
                    <td className="px-4 py-3">
                      <span className={`text-xs font-medium ${(p.confidence ?? 0) < 50 ? "text-red-500" : (p.confidence ?? 0) < 80 ? "text-amber-500" : "text-emerald-600"}`}>
                        {p.confidence ?? 0}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span>{data.total} produtos total</span>
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
