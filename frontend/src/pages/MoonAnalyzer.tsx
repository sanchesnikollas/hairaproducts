import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { analyzeWithMoon, getMoonProfile, saveMoonProfile, getProducts } from '@/lib/api';
import type { MoonAnalysis } from '@/lib/api';
import type { Product } from '@/types/api';

const HAIR_TYPES = [
  { slug: 'liso', label: 'Liso' },
  { slug: 'ondulado', label: 'Ondulado' },
  { slug: 'cacheado', label: 'Cacheado' },
  { slug: 'crespo', label: 'Crespo' },
  { slug: 'oleoso', label: 'Oleoso' },
  { slug: 'seco', label: 'Seco' },
  { slug: 'misto', label: 'Misto' },
  { slug: 'normal', label: 'Normal' },
  { slug: 'com_quimica', label: 'Com química' },
  { slug: 'tingido', label: 'Tingido' },
  { slug: 'danificado', label: 'Danificado' },
  { slug: 'sensibilizado', label: 'Sensibilizado' },
  { slug: 'fino', label: 'Fino' },
  { slug: 'grosso', label: 'Grosso' },
];

function parseInci(text: string): string[] {
  // Split on commas, semicolons, or newlines; trim; remove empties
  return text
    .split(/[,;\n]/)
    .map((s) => s.trim().replace(/^[\-\*\•]\s*/, ''))
    .filter((s) => s.length > 1 && s.length < 100);
}

// Real-world sample taken from an Oe Nani shampoo (Shopify auto-blueprint)
// to give users an immediate "show me" experience.
const SAMPLE_INCI = [
  'Aqua', 'Sodium Laureth Sulfate', 'Cocamidopropyl Betaine',
  'Glycerin', 'Argan Oil', 'Panthenol', 'Cetearyl Alcohol',
  'Dimethicone', 'Phenoxyethanol', 'Parfum', 'Limonene',
].join(', ');
const SAMPLE_HAIR_TYPES = ['cacheado', 'seco'];

function scoreColor(score: number): string {
  if (score >= 0.6) return 'text-green-700 bg-green-50';
  if (score >= 0.2) return 'text-emerald-700 bg-emerald-50';
  if (score >= -0.2) return 'text-stone-700 bg-stone-50';
  if (score >= -0.6) return 'text-amber-700 bg-amber-50';
  return 'text-red-700 bg-red-50';
}

export default function MoonAnalyzer() {
  const [mode, setMode] = useState<'product' | 'inci'>('product');
  const [inciText, setInciText] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['cacheado']));
  const [useAi, setUseAi] = useState(true);
  const [analysis, setAnalysis] = useState<MoonAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Product selector
  const [productQuery, setProductQuery] = useState('');
  const [productResults, setProductResults] = useState<Product[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [searching, setSearching] = useState(false);

  // Profile
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [profileSavedAt, setProfileSavedAt] = useState<number | null>(null);

  // Carrega o perfil capilar salvo do usuário ao montar — pré-seleciona os tipos.
  useEffect(() => {
    getMoonProfile()
      .then((p) => {
        if (p.exists && p.hair_types.length > 0) {
          setSelectedTypes(new Set(p.hair_types));
        }
      })
      .catch(() => {/* sem perfil / não logado — mantém default */})
      .finally(() => setProfileLoaded(true));
  }, []);

  const ingredients = parseInci(inciText);
  const canAnalyze =
    selectedTypes.size > 0 &&
    (mode === 'product' ? !!selectedProduct : ingredients.length > 0);

  function toggleType(slug: string) {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function searchProducts(q: string) {
    setProductQuery(q);
    if (q.trim().length < 2) { setProductResults([]); return; }
    setSearching(true);
    try {
      const res = await getProducts({ search: q.trim(), per_page: 10 });
      setProductResults(res.items ?? []);
    } catch {
      setProductResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const req = mode === 'product' && selectedProduct
        ? { product_id: selectedProduct.id, hair_types: Array.from(selectedTypes), use_ai: useAi }
        : { inci: ingredients, hair_types: Array.from(selectedTypes), use_ai: useAi };
      const result = await analyzeWithMoon(req);
      setAnalysis(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao analisar');
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveProfile() {
    try {
      await saveMoonProfile(Array.from(selectedTypes));
      setProfileSavedAt(Date.now());
      setTimeout(() => setProfileSavedAt(null), 2500);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao salvar perfil');
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto p-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl font-semibold text-ink">🌙 Moon Analyzer</h1>
            <p className="mt-2 text-sm text-ink-muted">
              Escolha um produto do catálogo (ou cole o INCI), use seu perfil capilar salvo, e a Moon
              avalia a compatibilidade — com análise personalizada por IA.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setMode('inci');
              setInciText(SAMPLE_INCI);
              setSelectedTypes(new Set(SAMPLE_HAIR_TYPES));
              setAnalysis(null);
              setError(null);
            }}
            className="shrink-0 mt-2 px-3 py-1.5 text-xs rounded-full border border-cream-dark text-ink-muted hover:border-ink hover:text-ink transition-colors"
            title="Pré-popula a entrada com um shampoo real e perfil cacheado+seco"
          >
            ⚡ Carregar exemplo
          </button>
        </div>
      </motion.div>

      {/* Hair profile selector */}
      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-ink">
            Seu perfil capilar {profileLoaded && <span className="text-ink-faint">(carregado do seu perfil salvo)</span>}
          </h2>
          <button
            type="button"
            onClick={handleSaveProfile}
            disabled={selectedTypes.size === 0}
            className="px-3 py-1.5 text-xs rounded-full border border-cream-dark text-ink-muted hover:border-ink hover:text-ink transition-colors disabled:opacity-40"
          >
            {profileSavedAt ? '✓ Perfil salvo' : '💾 Salvar meu perfil'}
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {HAIR_TYPES.map((ht) => (
            <button
              key={ht.slug}
              onClick={() => toggleType(ht.slug)}
              className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
                selectedTypes.has(ht.slug)
                  ? 'border-ink bg-ink text-cream'
                  : 'border-cream-dark text-ink-muted hover:border-ink hover:text-ink'
              }`}
            >
              {ht.label}
            </button>
          ))}
        </div>
        <p className="text-xs text-ink-faint mt-2">
          Selecione 1 a 4 que melhor descrevem seu cabelo. "Salvar meu perfil" reusa essa seleção nas próximas análises.
        </p>
      </div>

      {/* Input: produto do catálogo OU colar INCI */}
      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <div className="flex gap-2 mb-4">
          <button
            onClick={() => setMode('product')}
            className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
              mode === 'product' ? 'border-ink bg-ink text-cream' : 'border-cream-dark text-ink-muted hover:border-ink'
            }`}
          >
            📦 Produto do catálogo
          </button>
          <button
            onClick={() => setMode('inci')}
            className={`px-3 py-1.5 text-xs rounded-full border transition-colors ${
              mode === 'inci' ? 'border-ink bg-ink text-cream' : 'border-cream-dark text-ink-muted hover:border-ink'
            }`}
          >
            ✍️ Colar INCI
          </button>
        </div>

        {mode === 'product' ? (
          <div>
            {selectedProduct ? (
              <div className="flex items-center justify-between rounded border border-cream-dark p-3">
                <div>
                  <div className="text-sm font-medium text-ink">{selectedProduct.product_name}</div>
                  <div className="text-xs text-ink-faint">{selectedProduct.brand_slug}</div>
                </div>
                <button
                  onClick={() => { setSelectedProduct(null); setProductQuery(''); setProductResults([]); }}
                  className="text-xs text-ink-muted hover:text-ink underline"
                >
                  trocar
                </button>
              </div>
            ) : (
              <div className="relative">
                <input
                  value={productQuery}
                  onChange={(e) => searchProducts(e.target.value)}
                  placeholder="Buscar produto do catálogo pelo nome (ex: máscara amend)…"
                  className="w-full p-3 text-sm rounded border border-cream-dark focus:border-ink focus:outline-none"
                />
                {searching && <span className="absolute right-3 top-3 text-xs text-ink-faint">buscando…</span>}
                {productResults.length > 0 && (
                  <div className="mt-1 max-h-56 overflow-auto rounded border border-cream-dark divide-y divide-cream">
                    {productResults.map((p) => (
                      <button
                        key={p.id}
                        onClick={() => { setSelectedProduct(p); setProductResults([]); }}
                        className="block w-full text-left px-3 py-2 text-sm hover:bg-cream/50"
                      >
                        <span className="text-ink">{p.product_name}</span>
                        <span className="text-ink-faint text-xs"> · {p.brand_slug}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ) : (
          <textarea
            value={inciText}
            onChange={(e) => setInciText(e.target.value)}
            placeholder="Cole aqui a lista de ingredientes do rótulo (separados por vírgula). Exemplo:&#10;Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Dimethicone, Argan Oil, Phenoxyethanol, Parfum, Limonene"
            className="w-full h-32 p-3 text-sm rounded border border-cream-dark focus:border-ink focus:outline-none resize-none"
          />
        )}

        <div className="flex items-center justify-between mt-3">
          <label className="flex items-center gap-2 text-xs text-ink-muted cursor-pointer">
            <input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} className="accent-ink" />
            🤖 Análise personalizada por IA
          </label>
          <button
            onClick={runAnalysis}
            disabled={!canAnalyze || loading}
            className="px-4 py-2 text-sm rounded bg-ink text-cream hover:bg-ink/90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Analisando…' : '🌙 Analisar com a Moon'}
          </button>
        </div>
        {mode === 'inci' && (
          <p className="text-xs text-ink-faint mt-2">
            {ingredients.length} ingrediente{ingredients.length !== 1 ? 's' : ''} detectado{ingredients.length !== 1 ? 's' : ''}
          </p>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>
      )}

      {/* Results */}
      {analysis && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
          {/* Score card */}
          <div className={`rounded-lg p-6 ${scoreColor(analysis.overall_score)}`}>
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2 text-xs uppercase tracking-wide opacity-70">
                  Score geral
                  <span
                    className="inline-flex items-center justify-center w-4 h-4 text-[10px] rounded-full border border-current opacity-80 cursor-help"
                    title="Score de -1 (incompatível) a +1 (ideal). Verde >+0.3, neutro entre -0.3 e +0.3, âmbar/vermelho <-0.3. Calculado pela média ponderada dos ingredientes (primeiros 5 pesam mais)."
                  >
                    ?
                  </span>
                </div>
                <div className="text-4xl font-display font-bold mt-1">
                  {analysis.overall_score >= 0 ? '+' : ''}{analysis.overall_score.toFixed(2)}
                </div>
                <div className="text-sm mt-2 font-medium">{analysis.interpretation}</div>
              </div>
              <div className="text-right text-xs opacity-70">
                <div>Cobertura</div>
                <div className="text-xl font-semibold mt-1">{analysis.coverage_pct}%</div>
                <div>{analysis.ingredients_categorized} de {analysis.ingredients_total} mapeados</div>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-current/10 text-[11px] opacity-70 leading-relaxed">
              <strong>Como ler:</strong> &minus;1 incompatível · 0 neutro · +1 ideal. Cobertura mostra
              quantos ingredientes a Moon reconhece — quanto maior, mais confiável o score.
            </div>
          </div>

          {/* Análise IA (camada consultiva sobre o score) */}
          {analysis.ai_analysis && (
            <div className="rounded-lg border border-violet-200 bg-violet-50/40 p-5">
              <h3 className="text-sm font-semibold text-violet-900 mb-2">🤖 Análise da Moon (IA)</h3>
              <p className="text-sm text-violet-950 leading-relaxed">{analysis.ai_analysis.summary}</p>

              {analysis.ai_analysis.synergies?.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-medium text-violet-900 mb-1">Sinergias entre ingredientes</div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-violet-800">
                    {analysis.ai_analysis.synergies.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              {analysis.ai_analysis.personalized_alerts?.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-medium text-violet-900 mb-1">Alertas para o seu perfil</div>
                  <ul className="list-disc list-inside space-y-1 text-xs text-violet-800">
                    {analysis.ai_analysis.personalized_alerts.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                </div>
              )}

              {analysis.ai_analysis.recommendation && (
                <p className="mt-3 text-sm text-violet-950">
                  <span className="font-medium">Recomendação:</span> {analysis.ai_analysis.recommendation}
                </p>
              )}
              <p className="mt-3 text-[10px] text-violet-400">
                Gerado por IA com base no INCI do produto — confira sempre o rótulo oficial.
              </p>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-4">
            {/* Alerts */}
            <div className="rounded-lg border border-amber-200 bg-amber-50/40 p-5">
              <h3 className="text-sm font-semibold text-amber-900 mb-3">⚠️ Alertas ({analysis.alerts.length})</h3>
              {analysis.alerts.length === 0 ? (
                <p className="text-xs text-amber-700">Nenhum alerta identificado.</p>
              ) : (
                <ul className="space-y-2">
                  {analysis.alerts.slice(0, 8).map((a, i) => (
                    <li key={i} className="text-xs">
                      <span className="font-medium text-amber-900">{a.name}</span>
                      <span className="text-amber-700"> → {a.hair_type}</span>
                      <p className="text-amber-700 italic mt-0.5">{a.reason}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Benefits */}
            <div className="rounded-lg border border-emerald-200 bg-emerald-50/40 p-5">
              <h3 className="text-sm font-semibold text-emerald-900 mb-3">✅ Benefícios ({analysis.benefits.length})</h3>
              {analysis.benefits.length === 0 ? (
                <p className="text-xs text-emerald-700">Nenhum benefício específico para o perfil.</p>
              ) : (
                <ul className="space-y-2">
                  {analysis.benefits.slice(0, 8).map((b, i) => (
                    <li key={i} className="text-xs">
                      <span className="font-medium text-emerald-900">{b.name}</span>
                      <span className="text-emerald-700"> → {b.hair_type}</span>
                      <p className="text-emerald-700 italic mt-0.5">{b.reason}</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Per-ingredient breakdown */}
          <details className="rounded-lg border border-cream-dark bg-white p-5">
            <summary className="cursor-pointer text-sm font-medium text-ink">
              Análise por ingrediente ({analysis.breakdown.length})
            </summary>
            <table className="w-full mt-4 text-xs">
              <thead className="text-ink-muted text-left">
                <tr>
                  <th className="pb-2">#</th>
                  <th className="pb-2">Ingrediente</th>
                  <th className="pb-2">Categoria</th>
                  <th className="pb-2 text-right">Peso</th>
                  <th className="pb-2 text-right">Match</th>
                </tr>
              </thead>
              <tbody>
                {analysis.breakdown.map((b, i) => (
                  <tr key={i} className="border-t border-cream">
                    <td className="py-1.5 text-ink-faint">{i + 1}</td>
                    <td className="py-1.5 text-ink">{b.name}</td>
                    <td className="py-1.5 text-ink-muted">{b.category || <span className="text-ink-faint italic">—</span>}</td>
                    <td className="py-1.5 text-right text-ink-muted">{b.weight}</td>
                    <td className="py-1.5 text-right">
                      {b.matches.length === 0 ? (
                        <span className="text-ink-faint">—</span>
                      ) : (
                        b.matches.map((m, j) => (
                          <span key={j} className={`inline-block px-1.5 py-0.5 rounded text-[10px] mr-1 ${
                            m.score > 0 ? 'bg-emerald-100 text-emerald-800'
                            : m.score < 0 ? 'bg-amber-100 text-amber-800'
                            : 'bg-stone-100 text-stone-700'
                          }`} title={m.reason}>
                            {m.hair_type}: {m.score > 0 ? '+' : ''}{m.score}
                          </span>
                        ))
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </motion.div>
      )}
    </div>
  );
}
