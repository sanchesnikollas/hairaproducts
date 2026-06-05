/**
 * Aba "Identidade & Tom" — edita as chaves de moon_config.
 * Layout: lista de chaves à esquerda, editor à direita.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Save, RotateCcw, AlertCircle, CheckCircle2 } from 'lucide-react';
import {
  listMoonConfig, updateMoonConfigKey, resetMoonConfigKey,
  type MoonConfigItem,
} from '@/lib/ops-api';

const KEY_LABELS: Record<string, string> = {
  'system_prompt': 'Prompt principal',
  'intent.saude_couro': 'Saúde do couro',
  'intent.analise_produto': 'Análise de produto',
  'intent.recomendacao': 'Recomendação',
  'intent.rotina_cuidado': 'Rotina / cronograma',
  'intent.geral': 'Conversa geral',
};

function fmtDate(s: string | null) {
  if (!s) return 'padrão do sistema';
  try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
}

export default function IdentityTab() {
  const [items, setItems] = useState<MoonConfigItem[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const res = await listMoonConfig();
      setItems(res.config);
      if (!selectedKey && res.config.length) {
        setSelectedKey(res.config[0].key);
        setDraft(res.config[0].value);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar');
    } finally {
      setLoading(false);
    }
  }, [selectedKey]);

  useEffect(() => { void refresh(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  const current = useMemo(
    () => items.find((it) => it.key === selectedKey) ?? null,
    [items, selectedKey],
  );

  function selectKey(key: string) {
    const it = items.find((x) => x.key === key);
    if (!it) return;
    setSelectedKey(key);
    setDraft(it.value);
    setSavedAt(null);
  }

  async function save() {
    if (!selectedKey) return;
    setSaving(true); setError(null);
    try {
      const updated = await updateMoonConfigKey(selectedKey, draft);
      setItems((prev) => prev.map((it) => (it.key === selectedKey ? updated : it)));
      setSavedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar');
    } finally {
      setSaving(false);
    }
  }

  async function resetKey() {
    if (!selectedKey) return;
    if (!confirm(`Restaurar "${KEY_LABELS[selectedKey] ?? selectedKey}" ao padrão do sistema?`)) return;
    setSaving(true); setError(null);
    try {
      const updated = await resetMoonConfigKey(selectedKey);
      setItems((prev) => prev.map((it) => (it.key === selectedKey ? updated : it)));
      setDraft(updated.value);
      setSavedAt(Date.now());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao restaurar');
    } finally {
      setSaving(false);
    }
  }

  const dirty = current ? draft !== current.value : false;
  const charCount = draft.length;
  const tokenEstimate = Math.floor(charCount / 4);

  return (
    <div className="flex gap-6 min-h-[60vh]">
      {/* Lista de chaves (esquerda) */}
      <aside className="w-72 shrink-0 space-y-1">
        <div className="text-xs uppercase tracking-wide text-ink-faint px-3 mb-1">Comportamento</div>
        {items.map((it) => {
          const label = KEY_LABELS[it.key] ?? it.key;
          const active = it.key === selectedKey;
          const custom = it.updated_at != null;
          return (
            <button
              key={it.key}
              onClick={() => selectKey(it.key)}
              className={`w-full text-left rounded-lg px-3 py-2.5 transition-colors flex items-center justify-between gap-2 ${
                active ? 'bg-ink text-white' : 'bg-white hover:bg-cream/60 text-ink border border-cream-dark'
              }`}
            >
              <span className="font-medium text-sm">{label}</span>
              {custom && (
                <span className={`text-[10px] rounded-full px-2 py-0.5 ${
                  active ? 'bg-white/15 text-white/80' : 'bg-[#ff5900]/10 text-[#ff5900]'
                }`}>
                  custom
                </span>
              )}
            </button>
          );
        })}
        {loading && <div className="text-xs text-ink-faint px-3">Carregando…</div>}
      </aside>

      {/* Editor (direita) */}
      <div className="flex-1 space-y-3 min-w-0">
        {!current && (
          <div className="rounded-xl border border-cream-dark bg-white p-8 text-center text-ink-muted">
            Selecione um item à esquerda para editar.
          </div>
        )}
        {current && (
          <>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="font-display text-lg font-semibold text-ink">
                  {KEY_LABELS[current.key] ?? current.key}
                </h3>
                {current.description && (
                  <p className="text-sm text-ink-muted mt-0.5">{current.description}</p>
                )}
                <p className="text-xs text-ink-faint mt-1">
                  Última edição: {fmtDate(current.updated_at)}
                  {current.updated_by ? ' • por admin' : ''}
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={resetKey}
                  disabled={saving || !current.updated_at}
                  className="text-sm rounded-lg border border-cream-dark px-3 py-1.5 text-ink-muted hover:text-ink hover:border-ink disabled:opacity-30 flex items-center gap-1.5"
                  title={current.updated_at ? 'Restaurar ao padrão' : 'Já está no padrão'}
                >
                  <RotateCcw size={14} /> Restaurar padrão
                </button>
                <button
                  onClick={save}
                  disabled={saving || !dirty}
                  className="text-sm rounded-lg bg-ink px-4 py-1.5 text-white font-medium hover:opacity-90 disabled:opacity-40 flex items-center gap-1.5"
                >
                  <Save size={14} /> {saving ? 'Salvando…' : 'Salvar'}
                </button>
              </div>
            </div>

            <textarea
              value={draft}
              onChange={(e) => { setDraft(e.target.value); setSavedAt(null); }}
              className="w-full min-h-[55vh] rounded-xl border border-cream-dark bg-white p-4 text-sm text-ink leading-relaxed font-mono outline-none focus:border-ink resize-vertical"
              placeholder="Escreva como Moon deve se comportar nesse cenário…"
            />

            <div className="flex items-center justify-between text-xs text-ink-faint">
              <span>{charCount.toLocaleString('pt-BR')} chars • ~{tokenEstimate.toLocaleString('pt-BR')} tokens</span>
              {savedAt && (
                <span className="flex items-center gap-1 text-emerald-600">
                  <CheckCircle2 size={12} /> Salvo — vale na próxima conversa
                </span>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-start gap-2">
                <AlertCircle size={16} className="shrink-0 mt-0.5" /> {error}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
