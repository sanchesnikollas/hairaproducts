import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import { Moon, Sparkles, Send, ThumbsUp, ThumbsDown, MessageSquarePlus, Trash2, MessageCircle } from 'lucide-react';
import { useAuth } from '@/lib/auth';
import {
  chatWithMoon, getHairProfile, sendMoonFeedback,
  listMoonConversations, getMoonConversation, deleteMoonConversation,
  type MoonChatMessage, type MoonChatResponse, type ConversationSummary,
} from '@/lib/api';

// Pre-made prompts shown in the empty state and as a quick bar above the input.
const SUGGESTED_PROMPTS: { label: string; prompt: string; emoji: string }[] = [
  { emoji: '📅', label: 'Cronograma capilar', prompt: 'Monte um cronograma capilar (hidratação, nutrição e reconstrução) para o meu tipo de cabelo.' },
  { emoji: '💧', label: 'Dicas de cuidado', prompt: 'Quais cuidados diários e semanais são ideais para o meu cabelo?' },
  { emoji: '🧴', label: 'Rotina de lavagem', prompt: 'Como deve ser a minha rotina de lavagem (frequência, low poo/no poo)?' },
  { emoji: '✨', label: 'Reduzir o frizz', prompt: 'Como controlar o frizz no meu cabelo? Que ingredientes ajudam?' },
  { emoji: '🚫', label: 'Ingredientes a evitar', prompt: 'Quais ingredientes eu deveria evitar nos produtos, considerando o meu perfil?' },
  { emoji: '🎯', label: 'Finalizador ideal', prompt: 'Qual tipo de finalizador combina com o meu cabelo?' },
];

// Minimal, XSS-safe formatter: **bold** + line breaks -> React nodes.
function formatMessage(text: string) {
  return text.split('\n').map((line, li) => (
    <span key={li}>
      {line.split(/(\*\*[^*]+\*\*)/g).map((part, pi) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={pi} className="font-semibold">{part.slice(2, -2)}</strong>
          : <span key={pi}>{part}</span>
      )}
      {li < text.split('\n').length - 1 && <br />}
    </span>
  ));
}

export default function MoonChat() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<MoonChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [summary, setSummary] = useState<string>('');
  const [lastAlternatives, setLastAlternatives] = useState<MoonChatResponse['alternatives']>([]);
  const [rated, setRated] = useState<Record<number, 'up' | 'down'>>({});
  // Persisted conversation state — null = new conversation will be created on first send.
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);

  const refreshConversations = useCallback(async () => {
    if (!user) return;
    try {
      const r = await listMoonConversations(user.id, 30);
      setConversations(r.conversations);
    } catch { /* ignore */ }
  }, [user]);

  useEffect(() => { refreshConversations(); }, [refreshConversations]);

  function startNew() {
    setConversationId(null);
    setMessages([]);
    setLastAlternatives([]);
    setRated({});
    setError(null);
  }

  async function openConversation(cid: string) {
    setLoading(true); setError(null);
    try {
      const d = await getMoonConversation(cid);
      setConversationId(d.conversation_id);
      setMessages(d.messages.map((m) => ({ role: m.role, content: m.content })));
      // restore last alternatives from the most recent assistant turn
      const lastA = [...d.messages].reverse().find((m) => m.role === 'assistant' && m.alternatives);
      setLastAlternatives((lastA?.alternatives ?? []) as MoonChatResponse['alternatives']);
      setRated({});
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao abrir conversa');
    } finally { setLoading(false); }
  }

  async function removeConversation(cid: string) {
    if (!confirm('Apagar essa conversa? Não dá pra desfazer.')) return;
    try {
      await deleteMoonConversation(cid);
      if (cid === conversationId) startNew();
      await refreshConversations();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao remover');
    }
  }

  async function rate(idx: number, rating: 'up' | 'down') {
    if (rated[idx]) return;
    setRated((prev) => ({ ...prev, [idx]: rating })); // optimistic
    try {
      await sendMoonFeedback({
        rating,
        message_content: messages[idx]?.content ?? '',
        user_message: messages[idx - 1]?.role === 'user' ? messages[idx - 1].content : undefined,
        profile_snapshot: { summary, hair_types: summary ? summary.split(' · ') : [] },
        user_id: user?.id,
      });
    } catch {
      setRated((prev) => { const n = { ...prev }; delete n[idx]; return n; }); // rollback
    }
  }

  useEffect(() => {
    if (!user) return;
    getHairProfile(user.id)
      .then((pr) => { setHasProfile(true); setSummary((pr.derived_hair_types ?? []).join(' · ')); })
      .catch(() => setHasProfile(false));
  }, [user]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, loading]);

  async function send(text: string) {
    const content = text.trim();
    if (!content || loading) return;
    const next: MoonChatMessage[] = [...messages, { role: 'user', content }];
    setMessages(next); setInput(''); setLoading(true); setError(null);
    try {
      // When the conversation already exists, the backend has the history —
      // send only the new turn to avoid duplicating it.
      const payloadMessages: MoonChatMessage[] = conversationId
        ? [{ role: 'user', content }]
        : next;
      const res = await chatWithMoon({
        messages: payloadMessages, user_id: user?.id,
        conversation_id: conversationId ?? undefined,
      });
      setConversationId(res.conversation_id);
      setMessages([...next, { role: 'assistant', content: res.reply }]);
      setLastAlternatives(res.alternatives ?? []);
      if (res.profile_summary) setSummary(res.profile_summary);
      refreshConversations(); // sidebar reflects the new last_message_at
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Moon indisponível');
    } finally { setLoading(false); }
  }

  const firstName = user?.name?.split(' ')[0];

  return (
    <div className="max-w-6xl mx-auto h-[calc(100vh-3rem)] flex">
      {/* Conversation sidebar */}
      {sidebarOpen && (
        <aside className="w-64 shrink-0 border-r border-cream-dark flex flex-col bg-white/30">
          <div className="px-3 py-3 border-b border-cream-dark flex items-center gap-2">
            <button onClick={startNew}
              className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 text-sm rounded-full bg-ink text-cream hover:bg-ink/90">
              <MessageSquarePlus size={14} /> Nova conversa
            </button>
            <button onClick={() => setSidebarOpen(false)} title="Esconder"
              className="p-1.5 text-ink-muted hover:text-ink">‹</button>
          </div>
          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
            {conversations.length === 0 && (
              <p className="text-xs text-ink-faint text-center mt-6 px-3">
                Nenhuma conversa ainda. Escreva uma pergunta abaixo pra começar 🌙
              </p>
            )}
            {conversations.map((c) => (
              <div key={c.conversation_id}
                onClick={() => openConversation(c.conversation_id)}
                className={`group flex items-start gap-2 px-2.5 py-2 rounded-lg cursor-pointer transition-colors ${
                  c.conversation_id === conversationId ? 'bg-cream' : 'hover:bg-cream/60'}`}>
                <MessageCircle size={13} className="text-ink-muted shrink-0 mt-0.5" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-ink line-clamp-2 leading-snug">
                    {c.title || 'Conversa sem título'}
                  </div>
                  <div className="text-[10px] text-ink-faint mt-0.5">
                    {c.message_count} {c.message_count === 1 ? 'mensagem' : 'mensagens'}
                  </div>
                </div>
                <button onClick={(e) => { e.stopPropagation(); removeConversation(c.conversation_id); }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-ink-faint hover:text-red-600 transition-opacity">
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
          </div>
        </aside>
      )}

      <div className={`flex-1 flex flex-col ${sidebarOpen ? '' : 'max-w-2xl mx-auto'}`}>
        {!sidebarOpen && (
          <button onClick={() => setSidebarOpen(true)} title="Ver conversas"
            className="absolute left-2 top-20 z-10 p-2 rounded-md bg-white border border-cream-dark text-ink-muted hover:text-ink">›</button>
        )}
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-cream-dark">
        <div className="flex items-center gap-3">
          <div className="grid place-items-center w-10 h-10 rounded-full bg-gradient-to-br from-[#ff5900] to-[#ff8a4c] text-white shadow-sm">
            <Moon size={18} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink leading-none">
              Moon <span className="text-[#ff5900] italic">chat</span>
            </h1>
            {summary && <p className="text-xs text-ink-muted mt-1">Perfil: {summary}</p>}
          </div>
        </div>
        <span className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> Online
        </span>
      </div>

      {hasProfile === false && (
        <div className="mx-6 mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
          Você ainda não tem um perfil capilar.{' '}
          <Link to="/ops/profile" className="underline font-medium">Preencher agora</Link> para
          a Moon dar recomendações sob medida.
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
        {messages.length === 0 && (
          <div className="space-y-5">
            <div className="flex gap-2.5">
              <div className="shrink-0 grid place-items-center w-8 h-8 rounded-full bg-[#ff5900]/10 text-[#ff5900]">
                <Moon size={15} />
              </div>
              <div className="text-sm text-ink bg-cream rounded-2xl rounded-tl-md px-4 py-3 max-w-[85%] leading-relaxed">
                Oi{firstName ? `, ${firstName}` : ''}! Sou a Moon 🌙 Posso montar seu cronograma, dar
                dicas de cuidado e analisar produtos pelo seu perfil. Por onde quer começar?
              </div>
            </div>
            {/* Pre-made prompt cards */}
            <div className="grid grid-cols-2 gap-2.5">
              {SUGGESTED_PROMPTS.map((s) => (
                <button key={s.label} onClick={() => send(s.prompt)}
                  className="flex items-start gap-2 text-left rounded-xl border border-cream-dark bg-white px-3.5 py-3 hover:border-[#ff5900] hover:shadow-sm transition-all">
                  <span className="text-base leading-none mt-0.5">{s.emoji}</span>
                  <span className="text-xs font-medium text-ink">{s.label}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
            className={`flex gap-2.5 ${m.role === 'user' ? 'justify-end' : ''}`}>
            {m.role === 'assistant' && (
              <div className="shrink-0 grid place-items-center w-8 h-8 rounded-full bg-[#ff5900]/10 text-[#ff5900]">
                <Moon size={15} />
              </div>
            )}
            <div className="flex flex-col max-w-[85%]">
              <div className={`text-sm px-4 py-3 leading-relaxed ${
                m.role === 'user'
                  ? 'bg-[#ff5900]/15 text-ink rounded-2xl rounded-tr-md'
                  : 'bg-cream text-ink rounded-2xl rounded-tl-md'}`}>
                {formatMessage(m.content)}
              </div>
              {m.role === 'assistant' && (
                <div className="flex items-center gap-1.5 mt-1.5 pl-1">
                  {rated[i] ? (
                    <span className="text-[11px] text-ink-faint">
                      {rated[i] === 'up' ? '👍 Obrigada pelo feedback!' : '👎 Anotado — vou melhorar.'}
                    </span>
                  ) : (
                    <>
                      <span className="text-[11px] text-ink-faint mr-0.5">Útil?</span>
                      <button onClick={() => rate(i, 'up')} title="Útil"
                        className="p-1 rounded-md text-ink-faint hover:text-emerald-600 hover:bg-emerald-50 transition-colors">
                        <ThumbsUp size={13} />
                      </button>
                      <button onClick={() => rate(i, 'down')} title="Não útil"
                        className="p-1 rounded-md text-ink-faint hover:text-red-600 hover:bg-red-50 transition-colors">
                        <ThumbsDown size={13} />
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        ))}

        {loading && (
          <div className="flex gap-2.5">
            <div className="shrink-0 grid place-items-center w-8 h-8 rounded-full bg-[#ff5900]/10 text-[#ff5900]">
              <Moon size={15} />
            </div>
            <div className="flex items-center gap-1 bg-cream rounded-2xl rounded-tl-md px-4 py-3.5">
              {[0, 1, 2].map((d) => (
                <span key={d} className="w-1.5 h-1.5 rounded-full bg-ink-faint animate-bounce"
                  style={{ animationDelay: `${d * 0.15}s` }} />
              ))}
            </div>
          </div>
        )}

        {lastAlternatives.length > 0 && !loading && (
          <div className="ml-10 rounded-xl border border-cream-dark bg-white/60 p-3.5">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-ink mb-2">
              <Sparkles size={13} className="text-[#ff5900]" /> Alternativas compatíveis no catálogo
            </div>
            <ul className="space-y-1.5">
              {lastAlternatives.map((a) => (
                <li key={a.product_id} className="text-xs text-ink-muted flex items-center justify-between gap-2">
                  <span>{a.name} <span className="text-ink-faint">· {a.brand}</span></span>
                  <span className="shrink-0 px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 font-medium">
                    {a.score >= 0 ? '+' : ''}{a.score}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {error && <div className="mx-6 rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">{error}</div>}

      {/* Quick prompts bar (after conversation starts) + input */}
      <div className="px-6 py-4 border-t border-cream-dark">
        {messages.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-3 -mb-1">
            {SUGGESTED_PROMPTS.map((s) => (
              <button key={s.label} onClick={() => send(s.prompt)} disabled={loading}
                className="shrink-0 px-3 py-1.5 text-xs rounded-full border border-cream-dark text-ink-muted hover:border-[#ff5900] hover:text-ink transition-colors disabled:opacity-40">
                {s.emoji} {s.label}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <input value={input} onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') send(input); }}
            placeholder="Pergunte à Moon"
            className="flex-1 px-4 py-3 text-sm rounded-full border border-cream-dark focus:border-[#ff5900] focus:outline-none" />
          <button onClick={() => send(input)} disabled={loading || !input.trim()}
            className="grid place-items-center w-12 h-12 rounded-full bg-[#ff5900] text-white hover:bg-[#ff5900]/90 disabled:opacity-40 transition-colors">
            <Send size={17} />
          </button>
        </div>
      </div>
      </div>
    </div>
  );
}
