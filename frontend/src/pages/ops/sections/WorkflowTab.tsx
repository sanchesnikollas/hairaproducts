/**
 * Aba "Como Moon decide" — visualização do fluxo de resposta.
 * Mostra os 8 passos do raciocínio + lista dinâmica das fontes da KB que
 * são consultadas em cada chat (busca /api/admin/knowledge).
 */
import { useEffect, useState } from 'react';
import {
  MessageSquare, Tag, User, BookOpen, FlaskConical, Boxes, Sparkles, Save,
  ChevronDown,
} from 'lucide-react';
import { listKnowledge, type KnowledgeChunkSummary } from '@/lib/ops-api';

interface Step {
  icon: typeof MessageSquare;
  number: number;
  title: string;
  description: string;
  color: string;       // tailwind text color
  conditional?: string; // se rodar só em alguns casos
}

const STEPS: Step[] = [
  {
    icon: MessageSquare,
    number: 1,
    title: 'Pergunta do usuário',
    description: 'O usuário escreve uma pergunta no chat. Moon usa o histórico recente da conversa pra entender contexto.',
    color: 'text-sky-600',
  },
  {
    icon: Tag,
    number: 2,
    title: 'Detectar intenção',
    description: 'Roteador classifica a pergunta em 1 de 5 intents: saúde do couro, análise de produto, recomendação, rotina ou geral.',
    color: 'text-purple-600',
  },
  {
    icon: User,
    number: 3,
    title: 'Carregar perfil capilar',
    description: 'Slug do usuário (cacheado 3A, oleoso, descolorido…) — derivado do questionário e usado pra personalizar a resposta.',
    color: 'text-emerald-600',
  },
  {
    icon: BookOpen,
    number: 4,
    title: 'Carregar material proprietário (base científica)',
    description: 'É aqui que entra o Compêndio Haira + os outros documentos das Doutoras. Tudo vira contexto pra Moon antes dela formular a resposta. Esse bloco fica em cache na Anthropic (5min) pra reduzir custo.',
    color: 'text-amber-600',
  },
  {
    icon: FlaskConical,
    number: 5,
    title: 'Análise INCI (condicional)',
    description: 'Se for intenção de análise/recomendação, Moon pontua cada ingrediente vs perfil do usuário (categoria × tipo de cabelo).',
    color: 'text-rose-600',
    conditional: 'só análise / recomendação',
  },
  {
    icon: Boxes,
    number: 6,
    title: 'Buscar alternativas no catálogo (condicional)',
    description: 'Se aplicável, traz top 3 produtos compatíveis do catálogo Haira (excluindo non_hair, hidden, blacklist).',
    color: 'text-orange-600',
    conditional: 'só análise / recomendação',
  },
  {
    icon: Sparkles,
    number: 7,
    title: 'Claude monta a resposta',
    description: 'Tudo isso (perfil + KB + INCI + alternativas + personalidade) vai pra Anthropic Claude Sonnet 4.5 com regras de embasamento e tom da Moon.',
    color: 'text-indigo-600',
  },
  {
    icon: Save,
    number: 8,
    title: 'Persistir + citar fonte',
    description: 'Resposta é gravada na conversa, com snapshot das fontes usadas (kb_sources, analysis, alternatives) pra auditoria futura.',
    color: 'text-slate-600',
  },
];

export default function WorkflowTab() {
  const [sources, setSources] = useState<KnowledgeChunkSummary[] | null>(null);
  useEffect(() => {
    listKnowledge()
      .then((r) => setSources(r.chunks))
      .catch(() => setSources([]));
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-display text-xl font-semibold text-ink">Como Moon decide</h2>
        <p className="text-sm text-ink-muted mt-1 max-w-2xl">
          O fluxo de 8 passos que acontece em cada pergunta. Você pode mudar o tom em{' '}
          <strong>Identidade &amp; Tom</strong> e o conteúdo em <strong>Material</strong> —
          o resto é automático.
        </p>
      </div>

      <ol className="space-y-3">
        {STEPS.map((step, idx) => {
          const Icon = step.icon;
          const last = idx === STEPS.length - 1;
          return (
            <li key={step.number} className="relative">
              <div className="rounded-2xl border border-cream-dark bg-white p-4 flex items-start gap-4">
                <div className={`w-10 h-10 rounded-full bg-cream/60 flex items-center justify-center shrink-0 ${step.color}`}>
                  <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-xs text-ink-faint font-mono">{String(step.number).padStart(2, '0')}</span>
                    <h3 className="font-display text-base font-semibold text-ink">{step.title}</h3>
                    {step.conditional && (
                      <span className="text-[10px] uppercase tracking-wide rounded-full bg-amber-50 text-amber-700 px-2 py-0.5">
                        {step.conditional}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-ink-muted mt-1 leading-relaxed">{step.description}</p>

                  {/* Lista dinâmica das fontes no passo 4 (carregar material) */}
                  {step.number === 4 && sources != null && (
                    <div className="mt-3 rounded-lg bg-cream/40 border border-cream-dark px-3 py-2.5">
                      <div className="text-[11px] uppercase tracking-wide text-ink-faint mb-1.5">
                        Materiais carregados nesse passo hoje:
                      </div>
                      {sources.length === 0 ? (
                        <p className="text-xs text-ink-muted italic">
                          Nenhum documento ainda — suba arquivos na aba <strong>Material</strong>.
                        </p>
                      ) : (
                        <ul className="space-y-0.5">
                          {sources.map((s) => {
                            const isCompendio = /comp[eê]ndio/i.test(s.source);
                            return (
                              <li key={s.source} className="flex items-baseline gap-2 text-xs">
                                <span className={isCompendio ? 'text-[#ff5900] font-medium' : 'text-ink'}>
                                  {isCompendio && '✦ '}
                                  {s.source}
                                </span>
                                <span className="text-ink-faint font-mono">
                                  ~{s.token_estimate.toLocaleString('pt-BR')} tokens
                                </span>
                                {isCompendio && (
                                  <span className="text-[10px] uppercase tracking-wide text-[#ff5900]/70">
                                    base científica
                                  </span>
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      <div className="mt-2 text-[11px] text-ink-faint">
                        Total: <strong className="text-ink">
                          {sources.reduce((a, b) => a + b.token_estimate, 0).toLocaleString('pt-BR')} tokens
                        </strong> · janela Claude Sonnet 4.5: 200.000
                      </div>
                    </div>
                  )}
                </div>
              </div>
              {!last && (
                <div className="flex justify-center my-1">
                  <ChevronDown size={18} className="text-ink-faint" />
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <div className="rounded-2xl border border-cream-dark bg-cream/40 p-4 text-sm text-ink-muted space-y-2">
        <p>
          <strong className="text-ink">Onde o Compêndio entra:</strong> no passo 4 — junto com os
          outros documentos das Doutoras. Ele é a base científica que a Moon consulta antes de
          formular qualquer resposta. Se a pergunta cair em saúde do couro, Moon ainda redireciona
          a um(a) dermatologista (passo 2 com intent <code className="text-ink">saude_couro</code>).
        </p>
        <p>
          <strong className="text-ink">Por que isso importa:</strong> a Moon não inventa. Cada
          resposta sai apoiada em (1) o material proprietário que vocês mandaram e (2) o catálogo
          real de produtos da Haira. Se faltar contexto, ela diz que não tem material — não
          improvisa.
        </p>
      </div>
    </div>
  );
}
