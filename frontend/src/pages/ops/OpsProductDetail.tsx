import { useState, useRef, useEffect, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsGetProduct, opsUpdateProduct } from "../../lib/ops-api";
import { fetchProductIngredients } from "../../lib/api";
import { RevisionTimeline } from "../../components/ops/RevisionTimeline";
import SaveBar from "../../components/ops/SaveBar";
import CategorySelect from "../../components/ops/CategorySelect";
import IngredientTagInput from "../../components/ops/IngredientTagInput";
import {
  HAIR_TYPES,
  HAIR_TYPE_LABELS,
  AUDIENCE_AGES,
  AUDIENCE_AGE_LABELS,
  FUNCTIONS,
  FUNCTION_LABELS,
} from "../../types/api";
import type { ProductIngredient } from "../../types/api";

type ProductData = Record<string, unknown>;

const EDITABLE_FIELDS = [
  "product_name", "description", "usage_instructions", "composition",
  "product_category", "status_editorial", "status_publicacao",
  "image_url_main", "price", "size_volume", "inci_raw",
  // Hair classification
  "ph", "hair_type_csv", "audience_age", "function_objective",
  "image_url_front", "image_url_back",
] as const;

function getEditSnapshot(product: ProductData): Record<string, string> {
  const snap: Record<string, string> = {};
  for (const key of EDITABLE_FIELDS) {
    if (key === "inci_raw") {
      const arr = product.inci_ingredients as string[] | undefined;
      snap[key] = arr && arr.length > 0 ? arr.join(", ") : "";
    } else if (key === "hair_type_csv") {
      const arr = product.hair_type as string[] | undefined;
      snap[key] = arr && arr.length > 0 ? arr.join(",") : "";
    } else {
      const val = product[key];
      snap[key] = val != null ? String(val) : "";
    }
  }
  return snap;
}

export default function OpsProductDetail() {
  const { id } = useParams<{ id: string }>();
  const [form, setForm] = useState<Record<string, string>>({});
  const originalRef = useRef<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [showIngredients, setShowIngredients] = useState(false);
  const [showFullHistory, setShowFullHistory] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [extractedData, setExtractedData] = useState<Record<string, unknown> | null>(null);

  const { data: product, loading, error, refetch } = useAPI(
    () => opsGetProduct(id!),
    [id],
  );

  const { data: ingredients } = useAPI<ProductIngredient[]>(
    () => fetchProductIngredients(id!),
    [id],
  );

  // Initialize form when product loads
  useEffect(() => {
    if (product) {
      const snap = getEditSnapshot(product);
      originalRef.current = snap;
      setForm(snap);
    }
  }, [product]);

  const isDirty = Object.keys(form).some(
    (key) => form[key] !== (originalRef.current[key] ?? ""),
  );

  // Warn on leave
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) { e.preventDefault(); }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  const updateField = useCallback((key: string, value: string) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleDiscard = () => {
    setForm({ ...originalRef.current });
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updates: Record<string, unknown> = {};
      for (const [key, val] of Object.entries(form)) {
        if (val !== (originalRef.current[key] ?? "")) {
          if (key === "price" || key === "ph") {
            updates[key] = val ? parseFloat(val) : null;
          } else if (key === "inci_raw") {
            updates["inci_ingredients"] = val ? val.split(",").map((s) => s.trim()).filter(Boolean) : [];
            updates["composition"] = val || null;
          } else if (key === "hair_type_csv") {
            updates["hair_type"] = val ? val.split(",").map((s) => s.trim()).filter(Boolean) : null;
          } else {
            updates[key] = val || null;
          }
        }
      }
      if (Object.keys(updates).length > 0) {
        await opsUpdateProduct(id!, updates);
        refetch();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <p className="text-ink-muted">Carregando produto...</p>;
  if (error) return <p className="text-coral">Erro: {error}</p>;
  if (!product) return null;

  const p = product as ProductData;
  const dataQuality = p.data_quality as { fields: Record<string, boolean>; filled: number; total: number; pct: number } | undefined;
  const productLabels = p.product_labels as { detected?: string[]; inferred?: string[] } | null;
  const inputCls = "w-full rounded-lg border border-cream-dark bg-cream px-3 py-2 text-sm text-ink outline-none focus:border-ink focus:bg-white transition-colors";
  const readonlyCls = "w-full rounded-lg border border-cream-dark/50 bg-cream/50 px-3 py-2 text-sm text-ink-muted";
  const labelCls = "mb-1 block text-xs text-ink-muted";
  const cardCls = "rounded-xl border border-cream-dark bg-white p-5";

  return (
    <div className="space-y-4">
      {/* Save Bar */}
      <SaveBar isDirty={isDirty} saving={saving} onSave={handleSave} onDiscard={handleDiscard} />

      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <Link to="/ops/products" className="hover:text-ink transition-colors">← Produtos</Link>
        <span>/</span>
        <span className="text-ink font-medium truncate max-w-sm">{String(p.product_name)}</span>
      </div>

      {/* Two column layout */}
      <div className="flex gap-6 items-start">
        {/* Main column */}
        <div className="flex-[2] space-y-5 min-w-0">
          {/* Card: Info Básica */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold text-ink mb-4">Informações básicas</h2>
            <div className="space-y-3">
              <div>
                <label className={labelCls}>Nome</label>
                <input type="text" value={form.product_name ?? ""} onChange={(e) => updateField("product_name", e.target.value)} className={inputCls} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Marca</label>
                  <div className={readonlyCls}>{String(p.brand_slug)}</div>
                </div>
                <div>
                  <label className={labelCls}>Categoria</label>
                  <CategorySelect value={form.product_category ?? ""} onChange={(v) => updateField("product_category", v)} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Preço</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-xs text-ink-muted">R$</span>
                    <input
                      type="number" step="0.01" min="0"
                      value={form.price ?? ""}
                      onChange={(e) => updateField("price", e.target.value)}
                      className={`${inputCls} pl-9`}
                      placeholder="0.00"
                    />
                  </div>
                </div>
                <div>
                  <label className={labelCls}>Volume</label>
                  <input type="text" value={form.size_volume ?? ""} onChange={(e) => updateField("size_volume", e.target.value)} className={inputCls} placeholder="ex: 300ml" />
                </div>
              </div>
              {typeof p.product_url === "string" && !p.product_url.startsWith("manual://") && (
                <div>
                  <label className={labelCls}>URL do produto</label>
                  <a href={String(p.product_url)} target="_blank" rel="noopener noreferrer" className="block truncate text-xs text-blue-500 hover:underline">
                    {String(p.product_url)}
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* Card: Conteúdo */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold text-ink mb-4">Conteúdo</h2>
            <div className="space-y-3">
              <div>
                <label className={labelCls}>Descrição</label>
                <textarea value={form.description ?? ""} onChange={(e) => updateField("description", e.target.value)} rows={3} className={inputCls} placeholder="Descrição do produto..." />
              </div>
              <div>
                <label className={labelCls}>Composição</label>
                <textarea value={form.composition ?? ""} onChange={(e) => updateField("composition", e.target.value)} rows={3} className={inputCls} placeholder="Composição completa..." />
              </div>
              <div>
                <label className={labelCls}>Modo de uso</label>
                <textarea value={form.usage_instructions ?? ""} onChange={(e) => updateField("usage_instructions", e.target.value)} rows={3} className={inputCls} placeholder="Instruções de uso..." />
              </div>
            </div>
          </div>

          {/* Card: INCI */}
          <div className={cardCls}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-ink">INCI</h2>
              </div>
              {String(p.verification_status) === "verified_inci" && (
                <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">verified</span>
              )}
            </div>

            <IngredientTagInput
              value={form.inci_raw ? form.inci_raw.split(",").map((s) => s.trim()).filter(Boolean) : []}
              onChange={(tags) => updateField("inci_raw", tags.join(", "))}
            />

            {/* Mapped ingredients toggle */}
            {ingredients && ingredients.length > 0 && (
              <div className="mt-3">
                <button
                  onClick={() => setShowIngredients(!showIngredients)}
                  className="text-xs text-blue-500 hover:text-blue-700 transition-colors"
                >
                  {showIngredients ? "Ocultar" : "Ver"} ingredientes mapeados ({ingredients.length}) →
                </button>
                {showIngredients && (
                  <div className="mt-2 space-y-1 max-h-64 overflow-y-auto">
                    {ingredients.map((pi, i) => (
                      <div key={i} className="flex items-center gap-3 rounded-lg px-2 py-1 text-sm hover:bg-cream">
                        <span className="w-5 text-right text-xs text-ink-muted">{pi.position}.</span>
                        <span className="flex-1 text-ink">{pi.raw_name}</span>
                        <span className="text-xs text-ink-muted">{pi.ingredient?.canonical_name}</span>
                        <span className={`text-xs ${pi.validation_status === "validated" ? "text-emerald-600" : "text-amber-500"}`}>
                          {pi.validation_status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Card: Classificação */}
          <div className={cardCls}>
            <h2 className="text-sm font-semibold text-ink mb-4">Classificação para algoritmo</h2>
            <div className="space-y-4">
              <div>
                <label className={labelCls}>Função / Objetivo declarado</label>
                <select
                  value={form.function_objective ?? ""}
                  onChange={(e) => updateField("function_objective", e.target.value)}
                  className={inputCls}
                >
                  <option value="">— não classificado —</option>
                  {FUNCTIONS.map((f) => (
                    <option key={f} value={f}>{FUNCTION_LABELS[f]}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className={labelCls}>Público / Idade</label>
                <div className="flex gap-2 flex-wrap">
                  {AUDIENCE_AGES.map((age) => (
                    <button
                      key={age}
                      type="button"
                      onClick={() => updateField("audience_age", age)}
                      className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                        form.audience_age === age
                          ? "bg-ink text-cream border-ink"
                          : "bg-cream text-ink-muted border-cream-dark hover:border-ink"
                      }`}
                    >
                      {AUDIENCE_AGE_LABELS[age]}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className={labelCls}>Tipo de cabelo (multi-valor)</label>
                <div className="flex gap-2 flex-wrap">
                  {HAIR_TYPES.map((ht) => {
                    const selected = (form.hair_type_csv ?? "").split(",").map(s => s.trim()).filter(Boolean);
                    const isOn = selected.includes(ht);
                    return (
                      <button
                        key={ht}
                        type="button"
                        onClick={() => {
                          const next = isOn
                            ? selected.filter((s) => s !== ht)
                            : [...selected, ht];
                          updateField("hair_type_csv", next.join(","));
                        }}
                        className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                          isOn
                            ? "bg-ink text-cream border-ink"
                            : "bg-cream text-ink-muted border-cream-dark hover:border-ink"
                        }`}
                      >
                        {HAIR_TYPE_LABELS[ht]}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className={labelCls}>pH (se disponível no rótulo)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="14"
                  value={form.ph ?? ""}
                  onChange={(e) => updateField("ph", e.target.value)}
                  className={inputCls}
                  placeholder="ex: 5.5"
                />
                <p className="mt-1 text-[10px] text-ink-muted">Valor numérico entre 0 e 14. Geralmente impresso no rótulo (verso).</p>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="flex-1 space-y-4 sticky top-16 min-w-[260px]">
          {/* Status */}
          <div className={cardCls}>
            <h3 className="text-sm font-semibold text-ink mb-3">Status</h3>
            <div className="space-y-3">
              <div>
                <label className={labelCls}>Editorial</label>
                <select
                  value={form.status_editorial ?? ""}
                  onChange={(e) => updateField("status_editorial", e.target.value)}
                  className={inputCls}
                >
                  <option value="">—</option>
                  <option value="pendente">Pendente</option>
                  <option value="em_revisao">Em Revisão</option>
                  <option value="aprovado">Aprovado</option>
                  <option value="corrigido">Corrigido</option>
                  <option value="rejeitado">Rejeitado</option>
                </select>
              </div>
              <div>
                <label className={labelCls}>Publicação</label>
                <select
                  value={form.status_publicacao ?? ""}
                  onChange={(e) => updateField("status_publicacao", e.target.value)}
                  className={inputCls}
                >
                  <option value="">—</option>
                  <option value="rascunho">Rascunho</option>
                  <option value="publicado">Publicado</option>
                  <option value="despublicado">Despublicado</option>
                </select>
              </div>
              <div className="flex items-center justify-between pt-1 border-t border-cream-dark/50">
                <span className="text-xs text-ink-muted">Verificação</span>
                <span className={`text-xs font-medium ${
                  String(p.verification_status) === "verified_inci" ? "text-emerald-600"
                  : String(p.verification_status) === "quarantined" ? "text-red-500"
                  : "text-amber-500"
                }`}>
                  {String(p.verification_status)}
                </span>
              </div>
              {typeof p.extraction_method === "string" && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-muted">Extração</span>
                  <span className="text-[10px] rounded bg-cream px-1.5 py-0.5 text-ink-muted">{String(p.extraction_method)}</span>
                </div>
              )}
            </div>
          </div>

          {/* Image + Photo Upload */}
          <div className={cardCls}>
            <h3 className="text-sm font-semibold text-ink mb-3">Imagem & Foto</h3>
            {form.image_url_main && (
              <img
                src={form.image_url_main}
                alt=""
                className="w-full h-28 rounded-lg border border-cream-dark object-contain bg-cream mb-2"
                onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
              />
            )}
            <input
              type="text"
              value={form.image_url_main ?? ""}
              onChange={(e) => updateField("image_url_main", e.target.value)}
              className={`${inputCls} text-xs mb-2`}
              placeholder="URL da imagem principal"
            />

            {/* Front / Back photo URLs */}
            <div className="grid grid-cols-2 gap-2 mb-2">
              <div>
                <label className={labelCls}>Frente</label>
                {form.image_url_front && (
                  <img
                    src={form.image_url_front}
                    alt=""
                    className="w-full h-20 rounded border border-cream-dark object-contain bg-cream mb-1"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                )}
                <input
                  type="text"
                  value={form.image_url_front ?? ""}
                  onChange={(e) => updateField("image_url_front", e.target.value)}
                  className={`${inputCls} text-[10px]`}
                  placeholder="URL frente"
                />
              </div>
              <div>
                <label className={labelCls}>Verso (rótulo INCI)</label>
                {form.image_url_back && (
                  <img
                    src={form.image_url_back}
                    alt=""
                    className="w-full h-20 rounded border border-cream-dark object-contain bg-cream mb-1"
                    onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  />
                )}
                <input
                  type="text"
                  value={form.image_url_back ?? ""}
                  onChange={(e) => updateField("image_url_back", e.target.value)}
                  className={`${inputCls} text-[10px]`}
                  placeholder="URL verso"
                />
              </div>
            </div>
            {/* Photo upload for INCI extraction */}
            <div className="border-t border-cream-dark/50 pt-2 mt-1">
              <label className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-cream-dark bg-cream/50 py-3 cursor-pointer hover:border-ink/30 transition-colors">
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file) return;
                    setExtracting(true);
                    setExtractedData(null);
                    try {
                      const token = localStorage.getItem("haira_token");
                      const formData = new FormData();
                      formData.append("file", file);
                      const resp = await fetch(`/api/ops/products/${id}/extract-from-photo`, {
                        method: "POST",
                        headers: { Authorization: `Bearer ${token}` },
                        body: formData,
                      });
                      const data = await resp.json();
                      if (data.status === "ok" && data.extracted) {
                        setExtractedData(data.extracted);
                      } else {
                        alert(data.message || "Erro na extração");
                      }
                    } catch (err) {
                      alert("Erro ao enviar foto");
                    } finally {
                      setExtracting(false);
                      e.target.value = "";
                    }
                  }}
                />
                {extracting ? (
                  <span className="text-xs text-ink-muted">Extraindo com IA...</span>
                ) : (
                  <>
                    <span className="text-lg">📷</span>
                    <span className="text-[10px] text-ink-muted mt-1">Foto da embalagem → extrair INCI</span>
                  </>
                )}
              </label>
            </div>
            {/* Extracted data confirmation */}
            {extractedData && (
              <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3 space-y-2">
                <p className="text-xs font-medium text-emerald-800">Dados extraídos da foto:</p>
                {Array.isArray(extractedData.inci_ingredients) && (
                  <p className="text-[10px] text-emerald-700">{(extractedData.inci_ingredients as string[]).length} ingredientes detectados</p>
                )}
                {typeof extractedData.product_name === "string" && (
                  <p className="text-[10px] text-emerald-700">Nome: {extractedData.product_name.substring(0, 50)}</p>
                )}
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => {
                      const ext = extractedData;
                      if (ext.inci_ingredients && Array.isArray(ext.inci_ingredients)) {
                        updateField("inci_raw", (ext.inci_ingredients as string[]).join(", "));
                      }
                      if (ext.product_name && !form.product_name) updateField("product_name", String(ext.product_name));
                      if (ext.description) updateField("description", String(ext.description));
                      if (ext.size_volume) updateField("size_volume", String(ext.size_volume));
                      if (ext.product_category) updateField("product_category", String(ext.product_category));
                      setExtractedData(null);
                    }}
                    className="rounded bg-emerald-600 px-2.5 py-1 text-[10px] font-medium text-white hover:bg-emerald-700"
                  >
                    Aplicar dados
                  </button>
                  <button
                    type="button"
                    onClick={() => setExtractedData(null)}
                    className="rounded border border-emerald-200 px-2.5 py-1 text-[10px] text-emerald-700 hover:bg-emerald-100"
                  >
                    Descartar
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Quality */}
          {dataQuality && (
            <div className={cardCls}>
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-semibold text-ink">Qualidade</h3>
                <span className={`text-lg font-semibold ${
                  dataQuality.pct >= 80 ? "text-emerald-600" : dataQuality.pct >= 50 ? "text-amber-500" : "text-red-500"
                }`}>
                  {dataQuality.pct}%
                </span>
              </div>
              <div className="h-1.5 rounded-full bg-cream-dark overflow-hidden mb-3">
                <div
                  className={`h-full rounded-full ${
                    dataQuality.pct >= 80 ? "bg-emerald-500" : dataQuality.pct >= 50 ? "bg-amber-400" : "bg-red-400"
                  }`}
                  style={{ width: `${dataQuality.pct}%` }}
                />
              </div>
              <div className="grid grid-cols-2 gap-1">
                {Object.entries(dataQuality.fields).map(([field, present]) => (
                  <div key={field} className={`flex items-center gap-1 text-[10px] ${present ? "text-emerald-600" : "text-red-400"}`}>
                    <span>{present ? "✓" : "✗"}</span>
                    <span>{field}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between border-t border-cream-dark/50 pt-2">
                <span className="text-xs text-ink-muted">Confiança</span>
                <span className={`text-xs font-medium ${
                  (p.confidence as number) >= 80 ? "text-emerald-600" : (p.confidence as number) >= 50 ? "text-amber-500" : "text-red-500"
                }`}>
                  {p.confidence as number}%
                </span>
              </div>
            </div>
          )}

          {/* Seals */}
          {productLabels && (productLabels.detected?.length || productLabels.inferred?.length) ? (
            <div className={cardCls}>
              <h3 className="text-sm font-semibold text-ink mb-3">Selos</h3>
              <div className="flex flex-wrap gap-1.5">
                {[...(productLabels.detected || []), ...(productLabels.inferred || [])].map((seal) => {
                  const info: Record<string, { label: string; color: string }> = {
                    sulfate_free: { label: "Sem Sulfato", color: "bg-emerald-100 text-emerald-700" },
                    silicone_free: { label: "Sem Silicone", color: "bg-blue-100 text-blue-700" },
                    paraben_free: { label: "Sem Parabeno", color: "bg-green-100 text-green-700" },
                    petrolatum_free: { label: "Sem Petrolato", color: "bg-teal-100 text-teal-700" },
                    dye_free: { label: "Sem Corante", color: "bg-purple-100 text-purple-700" },
                    low_poo: { label: "Low Poo", color: "bg-cyan-100 text-cyan-700" },
                    no_poo: { label: "No Poo", color: "bg-indigo-100 text-indigo-700" },
                    vegan: { label: "Vegano", color: "bg-lime-100 text-lime-700" },
                    cruelty_free: { label: "Cruelty Free", color: "bg-pink-100 text-pink-700" },
                    natural: { label: "Natural", color: "bg-amber-100 text-amber-700" },
                    organic: { label: "Orgânico", color: "bg-yellow-100 text-yellow-700" },
                    dermatologically_tested: { label: "Derma Testado", color: "bg-sky-100 text-sky-700" },
                    uv_protection: { label: "Proteção UV", color: "bg-orange-100 text-orange-700" },
                    thermal_protection: { label: "Proteção Térmica", color: "bg-red-100 text-red-700" },
                    fragrance_free: { label: "Sem Fragrância", color: "bg-stone-100 text-stone-700" },
                  };
                  const s = info[seal] || { label: seal.replace(/_/g, " "), color: "bg-gray-100 text-gray-600" };
                  return (
                    <span key={seal} className={`inline-block rounded-full px-2.5 py-1 text-[10px] font-medium ${s.color}`}>
                      {s.label}
                    </span>
                  );
                })}
              </div>
              {productLabels.detected && productLabels.detected.length > 0 && (
                <p className="mt-2 text-[10px] text-ink-muted">
                  {productLabels.detected.length} detectado{productLabels.detected.length > 1 ? "s" : ""} · {(productLabels.inferred || []).length} inferido{(productLabels.inferred || []).length > 1 ? "s" : ""} por INCI
                </p>
              )}
            </div>
          ) : null}

          {/* History */}
          <div className={cardCls}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-ink">Histórico</h3>
              <button
                onClick={() => setShowFullHistory(!showFullHistory)}
                className="text-xs text-blue-500 hover:text-blue-700 transition-colors"
              >
                {showFullHistory ? "Ocultar" : "Ver tudo →"}
              </button>
            </div>
            {showFullHistory ? (
              <RevisionTimeline productId={id!} />
            ) : (
              <p className="text-xs text-ink-muted">Clique "Ver tudo" para o histórico completo</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
