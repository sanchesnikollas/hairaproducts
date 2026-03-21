import { useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsListProducts, opsBatchUpdate, opsCreateProduct } from "../../lib/ops-api";
import { useAuth } from "../../lib/auth";

type DataQuality = { fields: Record<string, boolean>; filled: number; total: number; pct: number };

function QualityBar({ quality }: { quality: DataQuality }) {
  const missing = Object.entries(quality.fields).filter(([, v]) => !v).map(([k]) => k);
  const color = quality.pct >= 80 ? "bg-emerald-500" : quality.pct >= 50 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-cream-dark overflow-hidden" title={missing.length > 0 ? `Falta: ${missing.join(", ")}` : "Completo"}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${quality.pct}%` }} />
      </div>
      <span className={`text-[10px] tabular-nums font-medium ${quality.pct >= 80 ? "text-emerald-600" : quality.pct >= 50 ? "text-amber-600" : "text-red-500"}`}>
        {quality.filled}/{quality.total}
      </span>
    </div>
  );
}

function CreateProductModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ brand_slug: "", product_name: "", description: "", product_category: "", product_url: "" });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.brand_slug || !form.product_name) return;
    setSaving(true);
    try {
      await opsCreateProduct({
        brand_slug: form.brand_slug,
        product_name: form.product_name,
        description: form.description || undefined,
        product_category: form.product_category || undefined,
        product_url: form.product_url || undefined,
      });
      onCreated();
      onClose();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao criar produto");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onClose}>
      <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-ink mb-4">Novo Produto</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Brand Slug *</label>
            <input required value={form.brand_slug} onChange={(e) => setForm({ ...form, brand_slug: e.target.value })}
              placeholder="ex: salon-line"
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Nome do Produto *</label>
            <input required value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })}
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">URL do Produto</label>
            <input value={form.product_url} onChange={(e) => setForm({ ...form, product_url: e.target.value })}
              placeholder="https://..."
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Categoria</label>
            <input value={form.product_category} onChange={(e) => setForm({ ...form, product_category: e.target.value })}
              placeholder="shampoo, condicionador..."
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Descricao</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={3}
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              {saving ? "Criando..." : "Criar Produto"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function OpsProducts() {
  const { isAdmin } = useAuth();
  const [brand, setBrand] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchAction, setBatchAction] = useState("");
  const [showCreate, setShowCreate] = useState(false);

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
      setSelected(new Set(data.items.map((p: { id: string }) => p.id)));
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
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-ink">Produtos</h1>
        {isAdmin && (
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            + Novo Produto
          </button>
        )}
      </div>

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
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Verificacao</th>
                  <th className="px-4 py-3">Confianca</th>
                  <th className="px-4 py-3">Completude</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p: {
                  id: string; product_name: string; brand_slug: string;
                  verification_status: string; status_editorial: string | null;
                  confidence: number; data_quality?: DataQuality;
                }) => (
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
                    <td className="px-4 py-3">
                      {p.data_quality ? (
                        <QualityBar quality={p.data_quality} />
                      ) : (
                        <span className="text-xs text-ink-muted">-</span>
                      )}
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

      {/* Create product modal */}
      {showCreate && (
        <CreateProductModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { refetch(); }}
        />
      )}
    </div>
  );
}
