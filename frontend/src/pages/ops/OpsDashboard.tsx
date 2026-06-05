import { Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { getDashboard } from "../../lib/ops-api";
import { Package, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import type { DashboardData } from "../../types/ops";

function KPICard({ label, value, sub, icon: Icon, color, to }: {
  label: string; value: string | number; sub?: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string; to?: string;
}) {
  const content = (
    <div className={`rounded-xl border border-cream-dark bg-white p-5${to ? " hover:border-ink/30 transition-colors" : ""}`}>
      <div className="flex items-center justify-between">
        <p className="text-xs text-ink-muted uppercase tracking-wider">{label}</p>
        <Icon size={18} className={color} />
      </div>
      <p className="mt-2 text-2xl font-semibold text-ink">{value}</p>
      {sub && <p className="mt-1 text-xs text-ink-muted">{sub}</p>}
    </div>
  );
  if (to) return <Link to={to}>{content}</Link>;
  return content;
}

export default function OpsDashboard() {
  const { data, loading, error } = useAPI<DashboardData>(() => getDashboard(), []);

  if (loading) return <p className="text-ink-muted">Carregando dashboard...</p>;
  if (error) return <p className="text-coral">Erro: {error}</p>;
  if (!data) return null;

  const { kpis } = data;

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-ink">Dashboard</h1>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        <KPICard label="Total Produtos" value={kpis.total_products} icon={Package} color="text-ink" />
        <KPICard label="Cobertura INCI" value={`${kpis.inci_coverage}%`} icon={CheckCircle} color="text-emerald-600" />
        <KPICard label="Pendentes" value={kpis.pending_review} icon={Clock} color="text-amber-500" to="/ops/products?status_editorial=pendente" />
        <KPICard label="Quarentena" value={kpis.quarantined} icon={AlertTriangle} color="text-red-500" to="/ops/products?verification_status=quarantined" />
        <KPICard label="Publicados" value={kpis.published} icon={CheckCircle} color="text-emerald-600" to="/ops/products?status_publicacao=publicado" />
        <KPICard label="Confiança Média" value={`${kpis.avg_confidence}%`} icon={Package} color="text-ink-muted" sub="Completude + parsing + revisão" />
      </div>

      {/* Data Completeness */}
      <div className="rounded-xl border border-cream-dark bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-ink">Completude dos Dados</h2>
        <div className="space-y-3">
          {[
            { label: "INCI", pct: kpis.inci_coverage, color: "bg-emerald-500" },
            { label: "Categoria", pct: kpis.category_pct ?? 0, color: "bg-blue-500" },
            { label: "Descrição", pct: kpis.description_pct ?? 0, color: "bg-amber-500" },
            { label: "Imagem", pct: kpis.image_pct ?? 0, color: "bg-purple-500" },
            { label: "Volume", pct: kpis.volume_pct ?? 0, color: "bg-cyan-500" },
          ].map(({ label, pct, color }) => (
            <div key={label} className="flex items-center gap-3">
              <span className="text-xs text-ink-muted w-20">{label}</span>
              <div className="flex-1 h-2 rounded-full bg-cream-dark overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
              </div>
              <span className="text-xs font-medium text-ink tabular-nums w-12 text-right">{pct}%</span>
            </div>
          ))}
        </div>
      </div>

      {/* Two columns: Low confidence + Recent activity */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Low confidence products */}
        <div className="rounded-xl border border-cream-dark bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-ink">Baixa Confiança</h2>
          {data.low_confidence.length === 0 ? (
            <p className="text-xs text-ink-muted">Nenhum produto com baixa confiança</p>
          ) : (
            <div className="space-y-2">
              {data.low_confidence.slice(0, 10).map((p) => (
                <Link
                  key={p.id}
                  to={`/ops/products/${p.id}`}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm hover:bg-cream transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-ink">{p.product_name}</p>
                    <p className="text-xs text-ink-muted">{p.brand_slug}</p>
                  </div>
                  <span className={`ml-2 text-xs font-medium ${p.confidence < 30 ? "text-red-500" : "text-amber-500"}`}>
                    {p.confidence}%
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent activity */}
        <div className="rounded-xl border border-cream-dark bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-ink">Atividade Recente</h2>
          {data.recent_activity.length === 0 ? (
            <p className="text-xs text-ink-muted">Atividades aparecerão aqui após revisões de produtos</p>
          ) : (
            <div className="space-y-2">
              {data.recent_activity.slice(0, 10).map((r) => (
                <div key={r.revision_id} className="rounded-lg px-3 py-2 text-sm">
                  <p className="text-ink">
                    <span className="font-medium">{r.field_name}</span>
                    <span className="text-ink-muted"> em {r.entity_type}</span>
                  </p>
                  <p className="text-xs text-ink-muted">
                    {r.change_source} · {new Date(r.created_at).toLocaleString("pt-BR")}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
