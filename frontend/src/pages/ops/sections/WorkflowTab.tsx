/**
 * Aba "Como Moon decide" — anatomia da Moon.
 *
 * Mental model: o Compêndio é o CÉREBRO (o que ela sabe). Tudo em volta —
 * personalidade, perfil capilar, catálogo, INCI — são órgãos que servem o
 * cérebro. Sem o Compêndio, Moon é um Claude genérico. Com ele, vira a
 * inteligência capilar das Doutoras.
 *
 * Layout: hero do cérebro → 4 órgãos em órbita → fluxo curto de pergunta.
 */
import { useEffect, useState } from 'react';
import {
  Brain, MessageCircleHeart, UserCircle2, Boxes, FlaskConical,
  ArrowDown, Sparkles, Save, MessageSquare, Tag,
} from 'lucide-react';
import { listKnowledge, type KnowledgeChunkSummary } from '@/lib/ops-api';

interface Organ {
  icon: typeof MessageCircleHeart;
  emoji: string;
  name: string;
  role: string;       // o que esse órgão é
  function: string;   // o que ele faz pelo cérebro
  tab: string;        // onde se edita
  accent: string;     // tailwind colors
}

const ORGANS: Organ[] = [
  {
    icon: MessageCircleHeart,
    emoji: '🎭',
    name: 'Voz',
    role: 'Personalidade',
    function: 'Como o cérebro se expressa. Tom, ritmo, abordagem por intent.',
    tab: 'Identidade & Tom',
    accent: 'from-purple-50 to-purple-50/40 text-purple-700 border-purple-200',
  },
  {
    icon: UserCircle2,
    emoji: '👁️',
    name: 'Visão',
    role: 'Perfil capilar',
    function: 'Quem está perguntando. Tipo de cabelo, oleosidade, química, sensibilidade.',
    tab: 'Conversa Moon (questionário)',
    accent: 'from-emerald-50 to-emerald-50/40 text-emerald-700 border-emerald-200',
  },
  {
    icon: Boxes,
    emoji: '🗂️',
    name: 'Memória factual',
    role: 'Catálogo Haira',
    function: 'Produtos, marcas, INCI. O cérebro consulta antes de recomendar.',
    tab: 'Marcas & Produtos',
    accent: 'from-orange-50 to-orange-50/40 text-orange-700 border-orange-200',
  },
  {
    icon: FlaskConical,
    emoji: '🧬',
    name: 'Reflexo INCI',
    role: 'Pontuação de ingredientes',
    function: 'Cada ingrediente × tipo de cabelo. Roda automático em análises.',
    tab: 'Ingredientes (read-only)',
    accent: 'from-rose-50 to-rose-50/40 text-rose-700 border-rose-200',
  },
];

interface FlowStep {
  icon: typeof MessageSquare;
  label: string;
  detail: string;
}

const FLOW: FlowStep[] = [
  { icon: MessageSquare, label: 'Pergunta entra',  detail: 'Usuário escreve. Moon lê histórico curto.' },
  { icon: Tag,           label: 'Intent detectado', detail: 'Análise · recomendação · rotina · saúde do couro · geral.' },
  { icon: UserCircle2,   label: 'Visão ativada',    detail: 'Perfil capilar é carregado.' },
  { icon: Brain,         label: 'Cérebro consultado', detail: 'Compêndio (encriptado) entra em cache de prompt 5min.' },
  { icon: FlaskConical,  label: 'Reflexo + Memória', detail: 'Em análises, INCI + catálogo entram juntos.' },
  { icon: Sparkles,      label: 'Voz dá forma',     detail: 'Claude Sonnet 4.5 combina tudo com a personalidade.' },
  { icon: Save,          label: 'Resposta + traço',  detail: 'Gravado com snapshot das fontes pra auditoria.' },
];

export default function WorkflowTab() {
  const [sources, setSources] = useState<KnowledgeChunkSummary[] | null>(null);
  useEffect(() => {
    listKnowledge()
      .then((r) => setSources(r.chunks))
      .catch(() => setSources([]));
  }, []);

  const compendio = sources?.find((s) => /comp[eê]ndio/i.test(s.source));
  const outrasFontes = (sources ?? []).filter((s) => !/comp[eê]ndio/i.test(s.source));
  const totalTokens = (sources ?? []).reduce((a, b) => a + b.token_estimate, 0);

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-xl font-semibold text-ink">Anatomia da Moon</h2>
        <p className="text-sm text-ink-muted mt-1 max-w-2xl">
          O <strong className="text-ink">Compêndio é o cérebro</strong>. Tudo em volta — voz,
          visão, memória factual e reflexo INCI — são órgãos que servem o cérebro. Sem ele,
          Moon é só um Claude genérico.
        </p>
      </div>

      {/* ─── CÉREBRO (hero) ─── */}
      <section
        aria-labelledby="brain-heading"
        className="relative overflow-hidden rounded-3xl border border-[#ff5900]/20 bg-gradient-to-br from-[#ff5900]/5 via-amber-50/30 to-cream p-8"
      >
        {/* Glow atmospheric */}
        <div className="pointer-events-none absolute -top-20 -right-20 h-64 w-64 rounded-full bg-[#ff5900]/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 -left-16 h-56 w-56 rounded-full bg-amber-200/20 blur-3xl" />

        <div className="relative flex flex-col md:flex-row items-start md:items-center gap-6">
          {/* Brain circle */}
          <div className="shrink-0 relative">
            <div className="absolute inset-0 rounded-full bg-[#ff5900]/15 blur-xl animate-pulse" />
            <div className="relative w-28 h-28 rounded-full bg-gradient-to-br from-[#ff5900] to-orange-700 flex items-center justify-center shadow-xl shadow-[#ff5900]/30 ring-4 ring-white">
              <Brain size={56} className="text-white" strokeWidth={1.5} />
            </div>
          </div>

          {/* Brain copy */}
          <div className="flex-1 min-w-0">
            <div className="text-[11px] uppercase tracking-[0.15em] text-[#ff5900] font-semibold">
              Cérebro · base científica
            </div>
            <h3 id="brain-heading" className="font-display text-3xl font-semibold text-ink mt-1">
              Compêndio Haira
            </h3>
            <p className="text-sm text-ink-muted mt-2 max-w-xl leading-relaxed">
              O que a Moon <strong>sabe</strong>. Encriptado em repouso (AES-256-GCM). Carregado a
              cada pergunta dentro do prompt cache da Anthropic (TTL 5min) pra reduzir custo sem
              perder atualização instantânea.
            </p>

            {/* Live snapshot */}
            <div className="mt-4 flex flex-wrap items-center gap-3 text-xs">
              {compendio ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-white border border-[#ff5900]/30 px-3 py-1 font-medium text-ink">
                  <span className="text-[#ff5900]" aria-hidden>✦</span>
                  {compendio.source}
                  <span className="text-ink-faint font-mono ml-1">
                    ~{compendio.token_estimate.toLocaleString('pt-BR')} tk
                  </span>
                </span>
              ) : sources === null ? (
                <span
                  aria-busy="true"
                  aria-label="Carregando fontes da Moon"
                  className="inline-flex h-6 w-48 animate-pulse rounded-full bg-white/60 border border-[#ff5900]/15"
                />
              ) : (
                <span className="rounded-full bg-amber-50 border border-amber-200 text-amber-700 px-3 py-1">
                  Compêndio ainda não foi subido — faça upload em <strong>Material</strong>.
                </span>
              )}

              {outrasFontes.length > 0 && (
                <span className="rounded-full bg-white border border-cream-dark px-3 py-1 text-ink-muted">
                  +{outrasFontes.length} doc(s) de apoio
                </span>
              )}

              {totalTokens > 0 && (
                <span className="rounded-full bg-white border border-cream-dark px-3 py-1 text-ink-muted">
                  Total: <strong className="text-ink">{totalTokens.toLocaleString('pt-BR')}</strong> /{' '}
                  200.000 tokens da janela
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      {/* ─── ÓRGÃOS (4 em órbita) ─── */}
      <section aria-labelledby="organs-heading" className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h3 id="organs-heading" className="font-display text-lg font-semibold text-ink">
            Os órgãos que servem o cérebro
          </h3>
          <span className="text-[11px] uppercase tracking-wide text-ink-faint">
            cada um tem uma função única
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {ORGANS.map((organ) => {
            const Icon = organ.icon;
            return (
              <article
                key={organ.role}
                className={`rounded-2xl border bg-gradient-to-br ${organ.accent} p-5 transition-transform hover:-translate-y-0.5`}
              >
                <div className="flex items-start gap-3">
                  <div className="shrink-0 w-10 h-10 rounded-xl bg-white/70 backdrop-blur flex items-center justify-center">
                    <Icon size={20} strokeWidth={1.75} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-base">{organ.emoji}</span>
                      <span className="text-[11px] uppercase tracking-wide font-semibold opacity-80">
                        {organ.name}
                      </span>
                    </div>
                    <h4 className="font-display text-lg font-semibold text-ink mt-0.5">
                      {organ.role}
                    </h4>
                    <p className="text-sm text-ink-muted mt-1 leading-relaxed">
                      {organ.function}
                    </p>
                    <div className="mt-2.5 text-[11px] text-ink-faint">
                      Editado em: <strong className="text-ink">{organ.tab}</strong>
                    </div>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>

      {/* ─── FLUXO DE UMA PERGUNTA ─── */}
      <section aria-labelledby="flow-heading" className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h3 id="flow-heading" className="font-display text-lg font-semibold text-ink">
            Como cérebro e órgãos se juntam
          </h3>
          <span className="text-[11px] uppercase tracking-wide text-ink-faint">
            cada pergunta atravessa esse caminho
          </span>
        </div>

        <ol className="rounded-2xl border border-cream-dark bg-white overflow-hidden divide-y divide-cream-dark">
          {FLOW.map((step, idx) => {
            const Icon = step.icon;
            const isBrain = step.icon === Brain;
            return (
              <li key={step.label} className="relative">
                <div className={`flex items-start gap-4 p-4 ${isBrain ? 'bg-[#ff5900]/5' : ''}`}>
                  <div className="shrink-0 flex flex-col items-center gap-1">
                    <div
                      className={`w-9 h-9 rounded-full flex items-center justify-center ${
                        isBrain
                          ? 'bg-gradient-to-br from-[#ff5900] to-orange-700 text-white shadow-lg shadow-[#ff5900]/30'
                          : 'bg-cream/60 text-ink-muted'
                      }`}
                    >
                      <Icon size={16} strokeWidth={1.75} />
                    </div>
                    <span className="text-[10px] font-mono text-ink-faint">
                      {String(idx + 1).padStart(2, '0')}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0 pt-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="font-display text-sm font-semibold text-ink">{step.label}</h4>
                      {isBrain && (
                        <span className="text-[10px] uppercase tracking-wide rounded-full bg-[#ff5900] text-white px-2 py-0.5">
                          cérebro
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-ink-muted mt-0.5 leading-relaxed">{step.detail}</p>
                  </div>
                </div>
                {idx < FLOW.length - 1 && (
                  <div className="absolute left-[34px] -bottom-2 z-10">
                    <ArrowDown size={12} className="text-ink-faint" />
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      </section>

      {/* ─── NOTA FINAL ─── */}
      <aside className="rounded-2xl border border-cream-dark bg-cream/40 p-5 text-sm text-ink-muted space-y-2">
        <p>
          <strong className="text-ink">Por que o Compêndio é o cérebro:</strong> ele é a única
          parte que define o que a Moon <em>conhece de verdade</em>. A personalidade só molda
          como ela expressa esse conhecimento. O catálogo só dá exemplos concretos. O perfil só
          contextualiza. Tira o Compêndio e tudo o resto continua técnico — mas sem inteligência
          capilar das Doutoras.
        </p>
        <p>
          <strong className="text-ink">O que isso significa pra ela errar menos:</strong> se uma
          resposta saiu fraca, o primeiro lugar de olhar é se o Compêndio cobre aquele assunto.
          Personalidade ajustada não compensa falta de base científica.
        </p>
      </aside>
    </div>
  );
}
