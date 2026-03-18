import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsGetProduct, opsUpdateProduct } from "../../lib/ops-api";
import { fetchProductIngredients } from "../../lib/api";
import { RevisionTimeline } from "../../components/ops/RevisionTimeline";
import { useAuth } from "../../lib/auth";
import type { ProductIngredient } from "../../types/api";

type Tab = "info" | "ingredients" | "enrichment" | "history";

export default function OpsProductDetail() {
  const { id } = useParams<{ id: string }>();
  const { isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("info");
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editData, setEditData] = useState<Record<string, string>>({});

  const { data: product, loading, error, refetch } = useAPI(
    () => opsGetProduct(id!),
    [id],
  );

  const { data: ingredients } = useAPI<ProductIngredient[]>(
    () => fetchProductIngredients(id!),
    [id],
  );

  if (loading) return <p className="text-ink-muted">Carregando produto...</p>;
  if (error) return <p className="text-coral">Erro: {error}</p>;
  if (!product) return null;

  const startEdit = () => {
    setEditData({
      product_name: product.product_name || "",
      description: product.description || "",
      usage_instructions: product.usage_instructions || "",
      product_category: product.product_category || "",
      status_editorial: product.status_editorial || "",
      status_publicacao: product.status_publicacao || "",
    });
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditData({});
  };

  const saveEdit = async () => {
    setSaving(true);
    try {
      const updates: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(editData)) {
        const original = (product as Record<string, unknown>)[key];
        if (val !== (original ?? "")) {
          updates[key] = val || null;
        }
      }
      if (Object.keys(updates).length > 0) {
        await opsUpdateProduct(id!, updates);
      }
      setEditing(false);
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  const tabs: { key: Tab; label: string }[] = [
    { key: "info", label: "Informacoes" },
    { key: "ingredients", label: "Ingredientes" },
    { key: "enrichment", label: "Enriquecimento" },
    { key: "history", label: "Historico" },
  ];

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
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <Link to="/ops/products" className="hover:text-ink">Produtos</Link>
        <span>/</span>
        <span className="text-ink font-medium truncate max-w-xs">{product.product_name}</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-4">
          {product.image_url_main && (
            <img src={product.image_url_main} alt="" className="h-16 w-16 rounded-lg border border-cream-dark object-cover" />
          )}
          <div>
            <h1 className="text-lg font-semibold text-ink">{product.product_name}</h1>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <span className="text-sm text-ink-muted">{product.brand_slug}</span>
              {statusBadge(product.status_editorial)}
              <span className={`text-xs font-medium ${(product.confidence ?? 0) < 50 ? "text-red-500" : "text-emerald-600"}`}>
                {product.confidence ?? 0}% confianca
              </span>
            </div>
          </div>
        </div>
        {isAdmin && !editing && (
          <button onClick={startEdit} className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90">
            Editar
          </button>
        )}
        {editing && (
          <div className="flex gap-2">
            <button onClick={cancelEdit} className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream">
              Cancelar
            </button>
            <button onClick={saveEdit} disabled={saving} className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              {saving ? "Salvando..." : "Salvar"}
            </button>
          </div>
        )}
      </div>

      {/* Tabs */}
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

      {/* Tab content */}
      <div className="rounded-xl border border-cream-dark bg-white p-6">
        {activeTab === "info" && (
          <div className="space-y-4">
            {editing ? (
              <>
                <Field label="Nome" value={editData.product_name} onChange={(v) => setEditData({ ...editData, product_name: v })} />
                <Field label="Descricao" value={editData.description} onChange={(v) => setEditData({ ...editData, description: v })} textarea />
                <Field label="Modo de Uso" value={editData.usage_instructions} onChange={(v) => setEditData({ ...editData, usage_instructions: v })} textarea />
                <Field label="Categoria" value={editData.product_category} onChange={(v) => setEditData({ ...editData, product_category: v })} />
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="mb-1 block text-xs text-ink-muted">Status Editorial</label>
                    <select
                      value={editData.status_editorial}
                      onChange={(e) => setEditData({ ...editData, status_editorial: e.target.value })}
                      className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm"
                    >
                      <option value="">-</option>
                      <option value="pendente">Pendente</option>
                      <option value="em_revisao">Em Revisao</option>
                      <option value="aprovado">Aprovado</option>
                      <option value="corrigido">Corrigido</option>
                      <option value="rejeitado">Rejeitado</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-ink-muted">Status Publicacao</label>
                    <select
                      value={editData.status_publicacao}
                      onChange={(e) => setEditData({ ...editData, status_publicacao: e.target.value })}
                      className="w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm"
                    >
                      <option value="">-</option>
                      <option value="rascunho">Rascunho</option>
                      <option value="publicado">Publicado</option>
                      <option value="despublicado">Despublicado</option>
                    </select>
                  </div>
                </div>
              </>
            ) : (
              <>
                <InfoRow label="Nome" value={product.product_name} />
                <InfoRow label="Brand" value={product.brand_slug} />
                <InfoRow label="Categoria" value={product.product_category} />
                <InfoRow label="Verificacao" value={product.verification_status} />
                <InfoRow label="Status Operacional" value={product.status_operacional} />
                <InfoRow label="Status Editorial" value={product.status_editorial} />
                <InfoRow label="Status Publicacao" value={product.status_publicacao} />
                {product.description && <InfoRow label="Descricao" value={product.description} />}
                {product.usage_instructions && <InfoRow label="Modo de Uso" value={product.usage_instructions} />}
              </>
            )}
          </div>
        )}

        {activeTab === "ingredients" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink">INCI ({product.inci_ingredients?.length ?? 0} ingredientes)</h3>
            {product.inci_ingredients && product.inci_ingredients.length > 0 ? (
              <ol className="space-y-1">
                {product.inci_ingredients.map((ing, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-ink-light">
                    <span className="w-6 text-right text-xs text-ink-muted">{i + 1}.</span>
                    <span>{ing}</span>
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-xs text-ink-muted">Sem INCI disponivel</p>
            )}

            {ingredients && ingredients.length > 0 && (
              <>
                <h3 className="mt-6 text-sm font-semibold text-ink">Ingredientes Mapeados</h3>
                <div className="space-y-1">
                  {ingredients.map((pi, i) => (
                    <div key={i} className="flex items-center gap-3 rounded-lg px-2 py-1 text-sm hover:bg-cream">
                      <span className="w-6 text-right text-xs text-ink-muted">{pi.position}.</span>
                      <span className="flex-1 text-ink">{pi.raw_name}</span>
                      <span className="text-xs text-ink-muted">{pi.ingredient?.canonical_name}</span>
                      <span className={`text-xs ${pi.validation_status === "validated" ? "text-emerald-600" : "text-amber-500"}`}>
                        {pi.validation_status}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === "enrichment" && (
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-ink">Dados de Enriquecimento</h3>
            <EnrichmentSection label="Confidence Factors" data={product.confidence_factors} />
            <EnrichmentSection label="Interpretation Data" data={product.interpretation_data} />
            <EnrichmentSection label="Application Data" data={product.application_data} />
            <EnrichmentSection label="Decision Data" data={product.decision_data} />
          </div>
        )}

        {activeTab === "history" && (
          <div>
            <h3 className="mb-4 text-sm font-semibold text-ink">Historico de Revisoes</h3>
            <RevisionTimeline productId={id!} />
          </div>
        )}
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-start gap-4 border-b border-cream-dark/50 pb-3">
      <span className="w-32 flex-shrink-0 text-xs text-ink-muted uppercase tracking-wider">{label}</span>
      <span className="text-sm text-ink">{value || "-"}</span>
    </div>
  );
}

function Field({ label, value, onChange, textarea }: {
  label: string; value: string; onChange: (v: string) => void; textarea?: boolean;
}) {
  const cls = "w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink";
  return (
    <div>
      <label className="mb-1 block text-xs text-ink-muted">{label}</label>
      {textarea ? (
        <textarea value={value} onChange={(e) => onChange(e.target.value)} rows={3} className={cls} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} className={cls} />
      )}
    </div>
  );
}

function EnrichmentSection({ label, data }: { label: string; data: Record<string, unknown> | null | undefined }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div>
        <h4 className="text-xs font-medium text-ink-muted">{label}</h4>
        <p className="mt-1 text-xs text-ink-muted">Sem dados</p>
      </div>
    );
  }
  return (
    <div>
      <h4 className="text-xs font-medium text-ink-muted">{label}</h4>
      <pre className="mt-1 rounded-lg bg-cream p-3 text-xs text-ink overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
