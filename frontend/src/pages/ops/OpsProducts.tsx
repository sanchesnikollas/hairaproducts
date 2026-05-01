import { useState, useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsListProducts, opsBatchUpdate, opsCreateProduct } from "../../lib/ops-api";
import { useAuth } from "../../lib/auth";
import CategorySelect from "../../components/ops/CategorySelect";

type DataQuality = { fields: Record<string, boolean>; filled: number; total: number; pct: number };

function QualityBar({ quality }: { quality: DataQuality }) {
  const color = quality.pct >= 80 ? "bg-emerald-500" : quality.pct >= 50 ? "bg-amber-400" : "bg-red-400";
  const missing = Object.entries(quality.fields).filter(([, v]) => !v).map(([k]) => k);
  return (
    <div className="flex items-center gap-2" title={missing.length > 0 ? `Falta: ${missing.join(", ")}` : "Completo"}>
      <div className="w-14 h-1.5 rounded-full bg-cream-dark overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${quality.pct}%` }} />
      </div>
      <span className={`text-[10px] tabular-nums font-medium ${quality.pct >= 80 ? "text-emerald-600" : quality.pct >= 50 ? "text-amber-600" : "text-red-500"}`}>
        {quality.filled}/{quality.total}
      </span>
    </div>
  );
}

function CreateProductModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ brand_slug: "", product_name: "", description: "", product_category: "", product_url: "", image_url_main: "", price: "", size_volume: "" });
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
        image_url_main: form.image_url_main || undefined,
        price: form.price ? parseFloat(form.price) : undefined,
        size_volume: form.size_volume || undefined,
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
      <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-ink mb-4">Novo Produto</h2>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
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
              <CategorySelect value={form.product_category} onChange={(v) => setForm({ ...form, product_category: v })} />
            </div>
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Preço</label>
              <input type="number" step="0.01" value={form.price} onChange={(e) => setForm({ ...form, price: e.target.value })}
                placeholder="R$ 0.00"
                className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
            </div>
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Volume</label>
              <input value={form.size_volume} onChange={(e) => setForm({ ...form, size_volume: e.target.value })}
                placeholder="ex: 300ml"
                className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">URL da Imagem</label>
            <input value={form.image_url_main} onChange={(e) => setForm({ ...form, image_url_main: e.target.value })}
              placeholder="https://...imagem.jpg"
              className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink" />
          </div>
          <div>
            <label className="mb-1 block text-xs text-ink-muted">Descrição</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2}
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

function StatusBadge({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    pendente: "bg-amber-100 text-amber-700",
    em_revisao: "bg-blue-100 text-blue-700",
    aprovado: "bg-emerald-100 text-emerald-700",
    corrigido: "bg-teal-100 text-teal-700",
    rejeitado: "bg-red-100 text-red-700",
  };
  if (!status) return <span className="text-xs text-ink-muted">—</span>;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${colors[status] || "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

export default function OpsProducts() {
  const { isAdmin } = useAuth();
  const [searchParams] = useSearchParams();

  const [brand, setBrand] = useState(searchParams.get("brand") || "");
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status_editorial") || "");
  const [verificationFilter, setVerificationFilter] = useState(searchParams.get("verification_status") || "");
  const [gapFilter, setGapFilter] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [batchAction, setBatchAction] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const fetcher = useCallback(
    () => opsListProducts({
      brand: brand || undefined,
      status_editorial: statusFilter || undefined,
      verification_status: verificationFilter || undefined,
      gap: gapFilter || undefined,
      search: search || undefined,
      page,
    }),
    [brand, statusFilter, verificationFilter, gapFilter, search, page],
  );

  const { data, loading, error, refetch } = useAPI(fetcher, [brand, statusFilter, verificationFilter, gapFilter, search, page]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!data) return;
    if (selected.size === data.items.length) setSelected(new Set());
    else setSelected(new Set(data.items.map((p: { id: string }) => p.id)));
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

  const pillCls = (active: boolean) =>
    `rounded-full border px-3 py-1 text-xs font-medium transition-colors cursor-pointer ${
      active ? "bg-ink text-white border-ink" : "bg-white border-cream-dark text-ink-muted hover:border-ink/30"
    }`;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-ink">Produtos</h1>
          {data && <span className="text-sm text-ink-muted">{data.total}</span>}
        </div>
        {isAdmin && (
          <button
            onClick={() => setShowCreate(true)}
            className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            + Novo Produto
          </button>
        )}
      </div>

      {/* Search */}
      <div className="relative">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          type="text"
          placeholder="Buscar produtos..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full rounded-lg border border-cream-dark bg-white pl-10 pr-4 py-2.5 text-sm text-ink outline-none focus:border-ink transition-colors"
        />
      </div>

      {/* Filter pills */}
      <div className="flex flex-wrap items-center gap-2">
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
          className={pillCls(!!statusFilter)}
        >
          <option value="">Status ▾</option>
          <option value="pendente">Pendente</option>
          <option value="em_revisao">Em Revisão</option>
          <option value="aprovado">Aprovado</option>
          <option value="corrigido">Corrigido</option>
          <option value="rejeitado">Rejeitado</option>
        </select>
        <input
          type="text"
          placeholder="Marca"
          value={brand}
          onChange={(e) => { setBrand(e.target.value); setPage(1); }}
          className="w-28 rounded-full border border-cream-dark bg-white px-3 py-1 text-xs text-ink outline-none focus:border-ink placeholder:text-ink-muted"
        />
        <select
          value={verificationFilter}
          onChange={(e) => { setVerificationFilter(e.target.value); setPage(1); }}
          className={pillCls(!!verificationFilter)}
        >
          <option value="">Verificação ▾</option>
          <option value="verified_inci">Verified INCI</option>
          <option value="catalog_only">Catalog Only</option>
          <option value="quarantined">Quarantined</option>
        </select>
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
          <option value="sem_funcao">Sem Função</option>
          <option value="sem_tipo_cabelo">Sem Tipo de Cabelo</option>
          <option value="sem_ph">Sem pH</option>
        </select>
        {(statusFilter || brand || verificationFilter || gapFilter) && (
          <button
            onClick={() => { setStatusFilter(""); setBrand(""); setVerificationFilter(""); setGapFilter(""); setPage(1); }}
            className="text-xs text-ink-muted hover:text-ink transition-colors"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* Batch actions */}
      {isAdmin && selected.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg bg-blue-50 px-4 py-2">
          <span className="text-sm text-blue-700">{selected.size} selecionados</span>
          <select value={batchAction} onChange={(e) => setBatchAction(e.target.value)} className="rounded border border-blue-200 bg-white px-2 py-1 text-sm">
            <option value="">Ação em lote...</option>
            <option value="aprovado">Aprovar</option>
            <option value="rejeitado">Rejeitar</option>
            <option value="pendente">Voltar p/ Pendente</option>
          </select>
          <button onClick={handleBatchAction} disabled={!batchAction} className="rounded-lg bg-blue-600 px-3 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
            Aplicar
          </button>
        </div>
      )}

      {loading && <p className="text-ink-muted">Carregando...</p>}
      {error && <p className="text-coral">Erro: {error}</p>}

      {/* Table */}
      {data && (
        <>
          <div className="overflow-x-auto rounded-xl border border-cream-dark bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-dark text-left text-[10px] text-ink-muted uppercase tracking-wider">
                  {isAdmin && <th className="w-10 px-3 py-3"><input type="checkbox" onChange={toggleAll} checked={selected.size === data.items.length && data.items.length > 0} /></th>}
                  <th className="w-10 px-1 py-3"></th>
                  <th className="px-3 py-3">Produto</th>
                  <th className="px-3 py-3 w-24">Marca</th>
                  <th className="px-3 py-3 w-20">Status</th>
                  <th className="px-3 py-3 w-20">INCI</th>
                  <th className="px-3 py-3 w-20">Confiança</th>
                  <th className="px-3 py-3 w-20" title="Campos preenchidos de 8: nome, descrição, INCI, composição, modo de uso, categoria, imagem, preço">Qualidade</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p: {
                  id: string; product_name: string; brand_slug: string;
                  verification_status: string; status_editorial: string | null;
                  confidence: number; data_quality?: DataQuality;
                  image_url_main?: string; product_category?: string;
                  inci_count?: number;
                }) => (
                  <tr key={p.id} className="border-b border-cream-dark/50 hover:bg-cream/50 transition-colors group">
                    {isAdmin && (
                      <td className="px-3 py-2.5">
                        <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} />
                      </td>
                    )}
                    <td className="px-1 py-2.5">
                      {p.image_url_main ? (
                        <img src={p.image_url_main} alt="" className="h-8 w-8 rounded border border-cream-dark object-cover" />
                      ) : (
                        <div className="h-8 w-8 rounded border border-cream-dark bg-cream-dark/30" />
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <Link to={`/ops/products/${p.id}`} className="font-medium text-ink hover:underline group-hover:text-ink">
                        {p.product_name}
                      </Link>
                      {p.product_category && (
                        <span className="ml-2 text-[10px] text-ink-muted">{p.product_category}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-xs text-ink-muted">{p.brand_slug}</td>
                    <td className="px-3 py-2.5"><StatusBadge status={p.status_editorial} /></td>
                    <td className="px-3 py-2.5">
                      {p.verification_status === "verified_inci" ? (
                        <span className="text-xs text-emerald-600 font-medium">✓</span>
                      ) : (
                        <span className="text-xs text-red-400">✗</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className={`text-xs font-medium tabular-nums ${
                        (p.confidence ?? 0) >= 80 ? "text-emerald-600"
                        : (p.confidence ?? 0) >= 50 ? "text-amber-500"
                        : "text-red-500"
                      }`}>
                        {p.confidence ?? 0}%
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {p.data_quality ? <QualityBar quality={p.data_quality} /> : <span className="text-xs text-ink-muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span>{data.total} produtos</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                Anterior
              </button>
              <span className="flex items-center px-2 tabular-nums">Página {page}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={data.items.length < data.per_page} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                Próxima
              </button>
            </div>
          </div>
        </>
      )}

      {showCreate && <CreateProductModal onClose={() => setShowCreate(false)} onCreated={() => refetch()} />}
    </div>
  );
}
