import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { useAuth } from '@/lib/auth';
import { saveHairProfile, getHairProfile, type HairProfile } from '@/lib/api';

// Questionnaire mirrors the Figma "Plano Cliente" capture flow (2.3.1 / 2.3.2).
type Opt = { value: string; label: string };
type SingleQ = { key: keyof HairProfile; q: string; opts: Opt[] };

const SUBTYPES: Opt[] = [
  '1A', '1B', '1C', '2A', '2B', '2C', '3A', '3B', '3C', '4A', '4B', '4C',
].map((v) => ({ value: v, label: v })).concat([{ value: 'nao_sei', label: 'Não sei' }]);

const SINGLE_QUESTIONS: SingleQ[] = [
  { key: 'curl_type', q: 'Qual o seu tipo de cabelo?', opts: [
    { value: 'liso', label: 'Liso' }, { value: 'ondulado', label: 'Ondulado' },
    { value: 'cacheado', label: 'Cacheado' }, { value: 'crespo', label: 'Crespo' },
    { value: 'transicao', label: 'Transição Capilar' } ] },
  { key: 'curl_subtype', q: 'Tipo específico (curvatura)', opts: SUBTYPES },
  { key: 'color', q: 'Cor atual do cabelo', opts: [
    { value: 'preto', label: 'Preto' }, { value: 'castanho', label: 'Castanho' },
    { value: 'loiro', label: 'Loiro' }, { value: 'ruivo', label: 'Ruivo' },
    { value: 'grisalhos', label: 'Grisalhos' }, { value: 'outras', label: 'Outras' } ] },
  { key: 'volume', q: 'Volume atual', opts: [
    { value: 'pouco', label: 'Pouco' }, { value: 'medio', label: 'Médio' }, { value: 'muito', label: 'Muito' } ] },
  { key: 'thickness', q: 'Espessura (grossura) dos fios', opts: [
    { value: 'finos', label: 'Finos' }, { value: 'medios', label: 'Médios' }, { value: 'grossos', label: 'Grossos' } ] },
  { key: 'length', q: 'Comprimento', opts: [
    { value: 'muito_curto', label: 'Muito curto' }, { value: 'curto', label: 'Curto' }, { value: 'longo', label: 'Longo' } ] },
  { key: 'scalp_oiliness', q: 'Oleosidade do couro cabeludo', opts: [
    { value: 'baixa', label: 'Baixa' }, { value: 'normal', label: 'Normal' }, { value: 'alta', label: 'Alta' } ] },
  { key: 'dryness_damage', q: 'O comprimento fica ressecado/danificado/com frizz?', opts: [
    { value: 'nao', label: 'Não' }, { value: 'um_pouco', label: 'Um pouco' }, { value: 'bastante', label: 'Bastante' } ] },
  { key: 'heat_usage', q: 'Usa secador, chapinha ou babyliss?', opts: [
    { value: 'nunca', label: 'Nunca' }, { value: 'as_vezes', label: 'Às vezes' },
    { value: '1x_mes', label: '1x/mês' }, { value: '1_2_semana', label: '1-2/semana' },
    { value: '3_4_semana', label: '3-4/semana' }, { value: 'diariamente', label: 'Diariamente' } ] },
  { key: 'extensions', q: 'Usa alongamento ou mega hair?', opts: [
    { value: 'none', label: 'Não' }, { value: 'tic_tac', label: 'Tic Tac' },
    { value: 'locks', label: 'Locks' }, { value: 'fixo', label: 'Fixo' } ] },
  { key: 'wash_frequency', q: 'Frequência de lavagem', opts: [
    { value: 'diaria', label: 'Diária' }, { value: '4_5_semana', label: '4-5x/semana' },
    { value: '2_3_semana', label: '2-3x/semana' }, { value: 'semanal_ou_menos', label: '1x/semana ou menos' } ] },
  { key: 'sun_exposure', q: 'Exposição ao sol', opts: [
    { value: 'baixa', label: 'Baixa' }, { value: 'moderada', label: 'Moderada' }, { value: 'alta', label: 'Alta' } ] },
  { key: 'water_exposure', q: 'Exposição ao mar ou piscina', opts: [
    { value: 'nunca', label: 'Nunca/raramente' }, { value: 'ocasional', label: 'Ocasional' }, { value: 'frequente', label: 'Frequente' } ] },
];

const CHEMICAL_OPTS: Opt[] = [
  { value: 'coloracao', label: 'Coloração' },
  { value: 'descoloracao', label: 'Descoloração (luzes/balayage)' },
  { value: 'alisamento', label: 'Alisamento/Progressiva/Relaxamento' },
];

export default function HairProfileForm() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [p, setP] = useState<HairProfile>({ chemical_treatments: [] });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    getHairProfile(user.id).then(setP).catch(() => { /* no profile yet */ });
  }, [user]);

  function pick(key: keyof HairProfile, value: string) {
    setP((prev) => ({ ...prev, [key]: prev[key] === value ? null : value }));
    setSaved(false);
  }
  function toggleChem(value: string) {
    setP((prev) => {
      const cur = new Set(prev.chemical_treatments ?? []);
      cur.has(value) ? cur.delete(value) : cur.add(value);
      return { ...prev, chemical_treatments: [...cur] };
    });
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true); setError(null);
    try {
      await saveHairProfile(p, user?.id);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar');
    } finally { setSaving(false); }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto p-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display text-4xl font-semibold text-ink">Meu cabelo</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Responda para a Moon recomendar produtos sob medida. Leva menos de 2 minutos.
        </p>
      </motion.div>

      {SINGLE_QUESTIONS.map((sq) => (
        <div key={sq.key} className="rounded-lg border border-cream-dark bg-white p-5">
          <h2 className="text-sm font-medium text-ink mb-3">{sq.q}</h2>
          <div className="flex flex-wrap gap-2">
            {sq.opts.map((o) => (
              <button key={o.value} onClick={() => pick(sq.key, o.value)}
                className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                  p[sq.key] === o.value ? 'border-ink bg-ink text-cream'
                    : 'border-cream-dark text-ink-muted hover:border-ink hover:text-ink'}`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>
      ))}

      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <h2 className="text-sm font-medium text-ink mb-3">Passou por química recentemente? (pode marcar mais de uma)</h2>
        <div className="flex flex-wrap gap-2">
          {CHEMICAL_OPTS.map((o) => (
            <button key={o.value} onClick={() => toggleChem(o.value)}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                (p.chemical_treatments ?? []).includes(o.value) ? 'border-ink bg-ink text-cream'
                  : 'border-cream-dark text-ink-muted hover:border-ink hover:text-ink'}`}>
              {o.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-faint mt-2">Não marcar nada = cabelo natural.</p>
      </div>

      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <h2 className="text-sm font-medium text-ink mb-3">Tem queda, caspa, coceira ou sensibilidade no couro?</h2>
        <div className="flex gap-2">
          {[{ v: true, l: 'Sim' }, { v: false, l: 'Não' }].map((o) => (
            <button key={o.l} onClick={() => { setP((prev) => ({ ...prev, scalp_issues: prev.scalp_issues === o.v ? null : o.v })); setSaved(false); }}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                p.scalp_issues === o.v ? 'border-ink bg-ink text-cream'
                  : 'border-cream-dark text-ink-muted hover:border-ink hover:text-ink'}`}>
              {o.l}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

      <div className="flex items-center gap-3 sticky bottom-4">
        <button onClick={handleSave} disabled={saving}
          className="px-5 py-2.5 text-sm rounded-full bg-ink text-cream hover:bg-ink/90 disabled:opacity-40">
          {saving ? 'Salvando…' : saved ? '✓ Salvo' : 'Salvar perfil'}
        </button>
        {saved && (
          <button onClick={() => navigate('/ops/moon-chat')}
            className="px-5 py-2.5 text-sm rounded-full bg-[#ff5900] text-white hover:bg-[#ff5900]/90">
            Falar com a Moon 🌙
          </button>
        )}
      </div>
    </div>
  );
}
