import { useAPI } from "../../hooks/useAPI";
import { getProductHistory } from "../../lib/ops-api";
import type { RevisionEntry } from "../../types/ops";

export function RevisionTimeline({ productId }: { productId: string }) {
  const { data, loading } = useAPI<{ revisions: RevisionEntry[] }>(
    () => getProductHistory(productId),
    [productId],
  );

  if (loading) return <p className="text-xs text-ink-muted">Carregando historico...</p>;
  if (!data || data.revisions.length === 0) return <p className="text-xs text-ink-muted">Sem alteracoes registradas</p>;

  return (
    <div className="space-y-3">
      {data.revisions.map((r) => (
        <div key={r.revision_id} className="border-l-2 border-cream-dark pl-4">
          <p className="text-sm text-ink">
            <span className="font-medium">{r.field_name}</span>
            {r.old_value && <span className="text-ink-muted"> de &quot;{r.old_value}&quot;</span>}
            <span className="text-ink-muted"> para </span>
            <span className="font-medium">&quot;{r.new_value}&quot;</span>
          </p>
          <p className="text-xs text-ink-faint">
            {r.change_source} · {new Date(r.created_at).toLocaleString("pt-BR")}
            {r.change_reason && ` · ${r.change_reason}`}
          </p>
        </div>
      ))}
    </div>
  );
}
