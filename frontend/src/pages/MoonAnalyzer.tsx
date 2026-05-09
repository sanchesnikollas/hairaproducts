import { useState } from 'react';
import { motion } from 'motion/react';
import { analyzeWithMoon } from '@/lib/api';
import type { MoonAnalysis } from '@/lib/api';

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

function scoreColor(score: number): string {
  if (score >= 0.6) return 'text-green-700 bg-green-50';
  if (score >= 0.2) return 'text-emerald-700 bg-emerald-50';
  if (score >= -0.2) return 'text-stone-700 bg-stone-50';
  if (score >= -0.6) return 'text-amber-700 bg-amber-50';
  return 'text-red-700 bg-red-50';
}

export default function MoonAnalyzer() {
  const [inciText, setInciText] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set(['cacheado']));
  const [analysis, setAnalysis] = useState<MoonAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ingredients = parseInci(inciText);
  const canAnalyze = ingredients.length > 0 && selectedTypes.size > 0;

  function toggleType(slug: string) {
    setSelectedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  }

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeWithMoon(ingredients, Array.from(selectedTypes));
      setAnalysis(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro ao analisar');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto p-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="font-display text-4xl font-semibold text-ink">🌙 Moon Analyzer</h1>
        <p className="mt-2 text-sm text-ink-muted">
          Cole a lista INCI de qualquer produto. A Moon avalia compatibilidade com seu perfil capilar
          e identifica alertas e benefícios principais.
        </p>
      </motion.div>

      {/* Hair profile selector */}
      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <h2 className="text-sm font-medium text-ink mb-3">Seu perfil capilar</h2>
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
          Selecione 1 a 4 que melhor descrevem seu cabelo (ex: cacheado + seco + tingido).
        </p>
      </div>

      {/* INCI input */}
      <div className="rounded-lg border border-cream-dark bg-white p-5">
        <h2 className="text-sm font-medium text-ink mb-3">Lista INCI do produto</h2>
        <textarea
          value={inciText}
          onChange={(e) => setInciText(e.target.value)}
          placeholder="Cole aqui a lista de ingredientes do rótulo (separados por vírgula). Exemplo:&#10;Aqua, Sodium Laureth Sulfate, Cocamidopropyl Betaine, Glycerin, Dimethicone, Argan Oil, Phenoxyethanol, Parfum, Limonene"
          className="w-full h-32 p-3 text-sm rounded border border-cream-dark focus:border-ink focus:outline-none resize-none"
        />
        <div className="flex items-center justify-between mt-3">
          <span className="text-xs text-ink-faint">
            {ingredients.length} ingrediente{ingredients.length !== 1 ? 's' : ''} detectado{ingredients.length !== 1 ? 's' : ''}
          </span>
          <button
            onClick={runAnalysis}
            disabled={!canAnalyze || loading}
            className="px-4 py-2 text-sm rounded bg-ink text-cream hover:bg-ink/90 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? 'Analisando…' : '🌙 Analisar com a Moon'}
          </button>
        </div>
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
                <div className="text-xs uppercase tracking-wide opacity-70">Score geral</div>
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
          </div>

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
