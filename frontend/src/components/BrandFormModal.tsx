/**
 * Modal compartilhado pra criar/editar marca no registry.
 * Usado em BrandsDashboard (sem brand) e BrandPage (com brand).
 */
import { useState } from 'react';
import { X } from 'lucide-react';
import {
  createBrand, updateBrand,
  type BrandRegistryItem, type BrandCreatePayload,
} from '@/lib/ops-api';

interface Props {
  /** Marca pra editar; se null/undefined, modal abre vazio (criar). */
  brand?: BrandRegistryItem | null;
  /** Pré-preenche o slug e desabilita o campo (usado no fluxo Nova Marca contextual). */
  lockedSlug?: string;
  onClose: () => void;
  onSaved: (b: BrandRegistryItem) => void;
}

const COUNTRIES = ['Brasil', 'Internacional', 'Outros'] as const;
const STATUSES = [
  { value: 'active', label: 'Ativa' },
  { value: 'blocked', label: 'Bloqueada (Cloudflare/WAF)' },
  { value: 'blocked_maintenance', label: 'Bloqueada — manutenção' },
  { value: 'out_of_scope', label: 'Fora do escopo' },
] as const;
const PLATFORMS = ['', 'VTEX', 'Shopify', 'WooCommerce', 'Magento', 'Custom'] as const;
const PRIORITIES = [
  { value: '', label: '— sem prioridade' },
  { value: '1', label: '1 — alta' },
  { value: '2', label: '2 — média' },
  { value: '3', label: '3 — baixa' },
] as const;

const inputCls = "w-full rounded-lg border border-cream-dark bg-white px-3 py-2 text-sm text-ink outline-none focus:border-ink";

export default function BrandFormModal({ brand, lockedSlug, onClose, onSaved }: Props) {
  const isEdit = brand != null;
  const [form, setForm] = useState({
    brand_name: brand?.brand_name ?? '',
    brand_slug: brand?.brand_slug ?? lockedSlug ?? '',
    official_url_root: brand?.official_url_root ?? '',
    country: (brand?.country as typeof COUNTRIES[number] | undefined) ?? 'Brasil',
    priority: brand?.priority != null ? String(brand.priority) : '',
    status: brand?.status ?? 'active',
    platform: brand?.platform ?? '',
    notes: brand?.notes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.brand_name.trim()) {
      setError('Nome da marca é obrigatório');
      return;
    }
    setSaving(true); setError(null);
    try {
      const payload: BrandCreatePayload = {
        brand_name: form.brand_name.trim(),
        official_url_root: form.official_url_root.trim() || undefined,
        country: form.country || undefined,
        priority: form.priority ? Number(form.priority) : undefined,
        status: form.status as BrandCreatePayload['status'],
        platform: form.platform || undefined,
        notes: form.notes.trim() || undefined,
      };
      const result = isEdit
        ? await updateBrand(brand!.brand_slug, payload)
        : await createBrand({ ...payload, brand_slug: form.brand_slug.trim() || undefined });
      onSaved(result);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-2xl bg-white shadow-xl max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between px-6 py-4 border-b border-cream-dark">
          <div>
            <h2 className="font-display text-xl font-semibold text-ink">
              {isEdit ? `Editar marca: ${brand!.brand_name}` : 'Nova marca'}
            </h2>
            {isEdit && brand?.updated_at && (
              <p className="text-xs text-ink-faint mt-1">
                Última edição: {new Date(brand.updated_at).toLocaleString('pt-BR')}
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-ink-muted hover:text-ink" aria-label="Fechar">
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Nome *</label>
              <input
                required
                value={form.brand_name}
                onChange={(e) => setForm({ ...form, brand_name: e.target.value })}
                placeholder="ex: Salon Line"
                className={inputCls}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-ink-muted">
                Slug {!isEdit && <span className="text-ink-faint">(gerado do nome se vazio)</span>}
              </label>
              <input
                value={form.brand_slug}
                disabled={isEdit || !!lockedSlug}
                onChange={(e) => setForm({ ...form, brand_slug: e.target.value })}
                placeholder="ex: salon-line"
                className={`${inputCls} ${(isEdit || lockedSlug) ? 'opacity-60 bg-cream/40' : ''}`}
              />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-ink-muted">URL do site oficial</label>
            <input
              value={form.official_url_root}
              onChange={(e) => setForm({ ...form, official_url_root: e.target.value })}
              placeholder="https://..."
              className={inputCls}
            />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Origem</label>
              <select
                value={form.country}
                onChange={(e) => setForm({ ...form, country: e.target.value as typeof COUNTRIES[number] })}
                className={inputCls}
              >
                {COUNTRIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Prioridade</label>
              <select
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
                className={inputCls}
              >
                {PRIORITIES.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-ink-muted">Status</label>
              <select
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value })}
                className={inputCls}
              >
                {STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs text-ink-muted">Plataforma (e-commerce)</label>
            <select
              value={form.platform}
              onChange={(e) => setForm({ ...form, platform: e.target.value })}
              className={inputCls}
            >
              {PLATFORMS.map((p) => <option key={p} value={p}>{p || '— não definida'}</option>)}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs text-ink-muted">Notas internas</label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              rows={2}
              placeholder="ex: inci_on_site=sim, multi-categoria — apenas X% capilar"
              className={inputCls}
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="rounded-lg border border-cream-dark px-4 py-2 text-sm hover:bg-cream">
              Cancelar
            </button>
            <button type="submit" disabled={saving} className="rounded-lg bg-ink px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50">
              {saving ? 'Salvando…' : isEdit ? 'Salvar' : 'Criar marca'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
