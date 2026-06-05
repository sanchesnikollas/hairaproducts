/**
 * Aba "Auditoria" — viewer dos audit logs (admin only no backend).
 * 3 sub-views (Login, Ações Admin, Consultas Moon) + KPIs no topo.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  ShieldCheck, MessageCircle, UserCog, RefreshCw, AlertCircle,
} from 'lucide-react';
import {
  getAuditSummary, listAuthEvents, listAdminActions, listKbRetrievals,
  type AuditSummary, type AuthEvent, type AdminActionEvent, type KbRetrievalEvent,
} from '@/lib/ops-api';

type View = 'auth' | 'admin' | 'kb';

function fmtDate(s: string | null) {
  if (!s) return '—';
  try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
}

function EventBadge({ kind, text }: { kind: 'ok' | 'fail' | 'info'; text: string }) {
  const map = {
    ok: 'bg-emerald-50 text-emerald-700',
    fail: 'bg-rose-50 text-rose-700',
    info: 'bg-cream text-ink-muted',
  };
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${map[kind]}`}>{text}</span>;
}

function authBadgeKind(t: string): 'ok' | 'fail' | 'info' {
  if (t.endsWith('_ok')) return 'ok';
  if (t.endsWith('_fail')) return 'fail';
  return 'info';
}

export default function AuditTab() {
  const [view, setView] = useState<View>('auth');
  const [summary, setSummary] = useState<AuditSummary | null>(null);
  const [authEvents, setAuthEvents] = useState<AuthEvent[] | null>(null);
  const [adminActions, setAdminActions] = useState<AdminActionEvent[] | null>(null);
  const [kbRetrievals, setKbRetrievals] = useState<KbRetrievalEvent[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [s, a, ad, kb] = await Promise.all([
        getAuditSummary(),
        listAuthEvents(100),
        listAdminActions(100),
        listKbRetrievals(100),
      ]);
      setSummary(s);
      setAuthEvents(a.events);
      setAdminActions(ad.actions);
      setKbRetrievals(kb.retrievals);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao carregar audit');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">Auditoria</h2>
          <p className="text-sm text-ink-muted mt-1 max-w-2xl">
            Trilha imutável de quem fez o quê. Toda ação admin (editar personalidade,
            criar marca, subir KB), todo login e cada consulta da Moon viram uma linha aqui.
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
      {summary && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
              <ShieldCheck size={12} /> Logins
            </div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">
              {summary.auth.total}
            </div>
            <div className="text-[11px] text-ink-faint mt-1">
              {summary.auth.login_ok} ok · {summary.auth.login_fail} fail
              {summary.auth.fail_rate_pct != null && ` · ${summary.auth.fail_rate_pct}% fail rate`}
            </div>
          </div>
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
              <UserCog size={12} /> Ações Admin
            </div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">
              {summary.admin_actions.total}
            </div>
            <div className="text-[11px] text-ink-faint mt-1">
              {summary.admin_actions.top[0]?.action ?? 'sem registros ainda'}
            </div>
          </div>
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint flex items-center gap-1">
              <MessageCircle size={12} /> Consultas Moon
            </div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">
              {summary.kb_retrievals.total}
            </div>
            <div className="text-[11px] text-ink-faint mt-1">
              {Object.entries(summary.kb_retrievals.by_intent).map(([k, n]) => `${k}: ${n}`).join(' · ') || '—'}
            </div>
          </div>
        </div>
      )}

      {/* Sub-tabs */}
      <div className="flex gap-1 border-b border-cream-dark">
        {([
          ['auth', 'Login & Auth'],
          ['admin', 'Ações Admin'],
          ['kb', 'Consultas Moon'],
        ] as [View, string][]).map(([v, label]) => (
          <button
            key={v}
            onClick={() => setView(v)}
            className={`px-4 py-2 text-sm transition-colors ${
              view === v ? 'border-b-2 border-ink font-medium text-ink' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tables */}
      <div className="rounded-2xl border border-cream-dark bg-white overflow-hidden">
        {view === 'auth' && (
          <table className="w-full text-sm">
            <thead className="bg-cream/50 text-ink-muted text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3">Quando</th>
                <th className="text-left px-4 py-3">Evento</th>
                <th className="text-left px-4 py-3">Email</th>
                <th className="text-left px-4 py-3">IP</th>
                <th className="text-left px-4 py-3">Detalhe</th>
              </tr>
            </thead>
            <tbody>
              {authEvents?.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-faint">Sem eventos.</td></tr>
              )}
              {authEvents?.map((e) => (
                <tr key={e.event_id} className="border-t border-cream-dark">
                  <td className="px-4 py-3 text-ink-muted">{fmtDate(e.created_at)}</td>
                  <td className="px-4 py-3"><EventBadge kind={authBadgeKind(e.event_type)} text={e.event_type} /></td>
                  <td className="px-4 py-3 text-ink">{e.email ?? '—'}</td>
                  <td className="px-4 py-3 text-ink-muted font-mono text-xs">{e.ip_address ?? '—'}</td>
                  <td className="px-4 py-3 text-ink-muted text-xs">{e.detail ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {view === 'admin' && (
          <table className="w-full text-sm">
            <thead className="bg-cream/50 text-ink-muted text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3">Quando</th>
                <th className="text-left px-4 py-3">Ação</th>
                <th className="text-left px-4 py-3">Quem</th>
                <th className="text-left px-4 py-3">Alvo</th>
              </tr>
            </thead>
            <tbody>
              {adminActions?.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-ink-faint">
                  Nenhuma ação ainda. Edita uma marca ou personalidade da Moon e volta aqui.
                </td></tr>
              )}
              {adminActions?.map((a) => (
                <tr key={a.action_id} className="border-t border-cream-dark">
                  <td className="px-4 py-3 text-ink-muted">{fmtDate(a.created_at)}</td>
                  <td className="px-4 py-3"><EventBadge kind="info" text={a.action} /></td>
                  <td className="px-4 py-3 text-ink">{a.actor_email ?? a.actor_id}</td>
                  <td className="px-4 py-3 text-ink-muted text-xs">
                    {a.target_type && <span className="text-ink-faint">{a.target_type}/</span>}
                    {a.target_id ?? '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {view === 'kb' && (
          <table className="w-full text-sm">
            <thead className="bg-cream/50 text-ink-muted text-xs uppercase">
              <tr>
                <th className="text-left px-4 py-3">Quando</th>
                <th className="text-left px-4 py-3">Intent</th>
                <th className="text-left px-4 py-3">Hash da pergunta</th>
                <th className="text-left px-4 py-3">Fontes usadas</th>
                <th className="text-right px-4 py-3">Chunks</th>
              </tr>
            </thead>
            <tbody>
              {kbRetrievals?.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-faint">Nenhuma consulta ainda.</td></tr>
              )}
              {kbRetrievals?.map((r) => (
                <tr key={r.log_id} className="border-t border-cream-dark">
                  <td className="px-4 py-3 text-ink-muted">{fmtDate(r.created_at)}</td>
                  <td className="px-4 py-3"><EventBadge kind="info" text={r.intent ?? '—'} /></td>
                  <td className="px-4 py-3 text-ink-muted font-mono text-[11px]">{r.query_hash.slice(0, 24)}…</td>
                  <td className="px-4 py-3 text-ink-muted text-xs">
                    {r.kb_sources && r.kb_sources.length > 0 ? r.kb_sources.join(' · ') : '—'}
                  </td>
                  <td className="px-4 py-3 text-right text-ink tabular-nums">{r.chunk_count ?? '0'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="rounded-2xl border border-cream-dark bg-cream/40 p-4 text-sm text-ink-muted">
        <strong className="text-ink">Privacidade:</strong> a pergunta crua do usuário NÃO é
        armazenada — só um sha256 do texto normalizado. Isso permite detectar &quot;mesma
        dúvida recorrente&quot; sem guardar PII.
      </div>
    </div>
  );
}
