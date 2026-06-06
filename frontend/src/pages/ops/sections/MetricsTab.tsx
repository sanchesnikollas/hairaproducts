/**
 * Aba "Métricas" — feedback summary da Moon + recent downvotes.
 * Endpoint /moon/feedback/summary é admin-only no backend.
 */
import { useCallback, useEffect, useState } from 'react';
import { ThumbsUp, ThumbsDown, AlertCircle, RefreshCw, MessageCircleMore } from 'lucide-react';
import {
  getMoonFeedbackSummary,
  type MoonFeedbackSummary,
} from '@/lib/ops-api';

function fmtDate(s: string | null | undefined) {
  if (!s) return '—';
  try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
}

export default function MetricsTab() {
  const [data, setData] = useState<MoonFeedbackSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await getMoonFeedbackSummary()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Erro ao carregar'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">Métricas da Moon</h2>
          <p className="text-sm text-ink-muted mt-1">
            Feedback agregado das reviewers. Recent downvotes ajudam a identificar
            onde a Moon ainda erra.
          </p>
        </div>
        <button onClick={refresh} disabled={loading}
          className="p-2 rounded-lg border border-cream-dark text-ink-muted hover:text-ink hover:border-ink disabled:opacity-40">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" /> {error}
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-xl border border-cream-dark bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
            <MessageCircleMore size={12} /> Avaliações
          </div>
          <div className="text-3xl font-display font-semibold text-ink mt-1">
            {data ? data.total : '—'}
          </div>
        </div>
        <div className="rounded-xl border border-cream-dark bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
            <ThumbsUp size={12} /> Útil
          </div>
          <div className="text-3xl font-display font-semibold text-ink mt-1">
            {data ? (data.useful_pct == null ? '—' : `${data.useful_pct}%`) : '—'}
          </div>
          <div className="text-[11px] text-ink-faint mt-1 inline-flex items-center gap-1.5">
            {data && (
              <>
                <ThumbsUp size={11} className="text-emerald-600" /> {data.up}
                <span className="text-ink-faint/60">/</span>
                <ThumbsDown size={11} className="text-rose-600" /> {data.down}
              </>
            )}
          </div>
        </div>
        <div className="rounded-xl border border-cream-dark bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
            <ThumbsDown size={12} /> Downvotes recentes
          </div>
          <div className="text-3xl font-display font-semibold text-ink mt-1">
            {data ? data.recent_downvotes.length : '—'}
          </div>
        </div>
      </div>

      {/* Recent downvotes */}
      <div className="rounded-2xl border border-cream-dark bg-white overflow-hidden">
        <div className="px-4 py-3 border-b border-cream-dark">
          <h3 className="font-display font-semibold text-ink">Últimos downvotes</h3>
        </div>
        {data && data.recent_downvotes.length === 0 && (
          <div className="px-4 py-10 text-center text-sm text-ink-faint">
            Nenhum downvote registrado. Quando reviewers marcarem uma resposta como pouco útil, a pergunta e o trecho aparecem aqui.
          </div>
        )}
        {data && data.recent_downvotes.length > 0 && (
          <ul className="divide-y divide-cream-dark">
            {data.recent_downvotes.map((dv) => (
              <li key={dv.feedback_id} className="px-4 py-3 text-sm">
                <div className="text-xs text-ink-faint">{fmtDate(dv.created_at)}</div>
                {dv.user_message && (
                  <div className="text-ink mt-1">
                    <span className="text-ink-faint">Pergunta:</span> {dv.user_message}
                  </div>
                )}
                <div className="text-ink-muted mt-0.5 line-clamp-2">
                  <span className="text-ink-faint">Resposta Moon:</span> {dv.message_content}
                </div>
                {dv.comment && (
                  <div className="text-rose-600 mt-1 italic">
                    "{dv.comment}"
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
