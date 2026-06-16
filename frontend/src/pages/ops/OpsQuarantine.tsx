import { useState, useCallback, useMemo } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useAPI } from "../../hooks/useAPI";
import { opsListQuarantine, opsPromoteQuarantine } from "../../lib/ops-api";
import { InlineLoading } from "@/components/LoadingState";

function ReasonBadge({ code }: { code: string | null }) {
  if (!code) return <span className="text-[10px] text-ink-muted">—</span>;
  const colorMap: Record<string, string> = {
    "non_hair": "bg-red-100 text-red-700 border-red-200",
    "no_hair_keyword": "bg-amber-100 text-amber-700 border-amber-200",
    "bad_name_pattern_or_accessory": "bg-red-100 text-red-700 border-red-200",
    "name_garbage": "bg-red-100 text-red-700 border-red-200",
    "name_low_quality": "bg-amber-100 text-amber-700 border-amber-200",
    "name_editorial_or_invalid": "bg-amber-100 text-amber-700 border-amber-200",
    "domain_unofficial": "bg-purple-100 text-purple-700 border-purple-200",
    "no_image": "bg-blue-100 text-blue-700 border-blue-200",
  };
  const cls = colorMap[code] || "bg-gray-100 text-gray-700 border-gray-200";
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium ${cls}`}>
      {code}
    </span>
  );
}

export default function OpsQuarantine() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [brand, setBrand] = useState(searchParams.get("brand") || "");
  const [reasonCode, setReasonCode] = useState(searchParams.get("reason_code") || "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [promoting, setPromoting] = useState(false);

  const fetcher = useCallback(
    () => opsListQuarantine({
      brand: brand || undefined,
      rejection_code: reasonCode || undefined,
      search: search || undefined,
      page,
    }),
    [brand, reasonCode, search, page],
  );
  const { data, loading, error, refetch } = useAPI(fetcher, [brand, reasonCode, search, page]);

  const reasonOptions = useMemo(() => {
    if (!data?.reason_counts) return [];
    return Object.entries(data.reason_counts).sort((a, b) => b[1] - a[1]);
  }, [data]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (!data) return;
    if (selected.size === data.items.length) setSelected(new Set());
    else setSelected(new Set(data.items.map((p) => p.id)));
  };

  const handlePromote = async (target: "catalog_only" | "verified_inci") => {
    if (selected.size === 0) return;
    if (!confirm(`Promover ${selected.size} produto(s) para ${target}?`)) return;
    setPromoting(true);
    try {
      const res = await opsPromoteQuarantine(Array.from(selected), target);
      alert(`${res.promoted}/${res.requested} promovidos com sucesso.`);
      setSelected(new Set());
      refetch();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao promover");
    } finally {
      setPromoting(false);
    }
  };

  const updateUrlParam = (key: string, value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold text-ink">Quarentena</h1>
          {data && <span className="text-sm text-ink-muted">{data.total} produtos</span>}
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <input
          type="text"
          placeholder="Buscar produtos quarentenados..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="w-full rounded-lg border border-cream-dark bg-white px-4 py-2.5 text-sm text-ink outline-none focus:border-ink"
        />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="text"
          placeholder="Marca"
          value={brand}
          onChange={(e) => { setBrand(e.target.value); updateUrlParam("brand", e.target.value); setPage(1); }}
          className="w-32 rounded-full border border-cream-dark bg-white px-3 py-1 text-xs text-ink outline-none focus:border-ink"
        />
        <select
          value={reasonCode}
          onChange={(e) => { setReasonCode(e.target.value); updateUrlParam("reason_code", e.target.value); setPage(1); }}
          className="rounded-full border border-cream-dark bg-white px-3 py-1 text-xs text-ink-muted cursor-pointer"
        >
          <option value="">Motivo ▾ (todos)</option>
          {reasonOptions.map(([code, count]) => (
            <option key={code} value={code}>{code} ({count})</option>
          ))}
        </select>
        {(brand || reasonCode) && (
          <button
            onClick={() => { setBrand(""); setReasonCode(""); setSearchParams({}, { replace: true }); setPage(1); }}
            className="text-xs text-ink-muted hover:text-ink"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* Batch actions */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-cream-dark bg-white p-3">
          <span className="text-sm text-ink">{selected.size} selecionado(s)</span>
          <div className="flex gap-2">
            <button
              disabled={promoting}
              onClick={() => handlePromote("catalog_only")}
              className="rounded-lg border border-cream-dark px-3 py-1.5 text-sm hover:bg-cream disabled:opacity-50"
            >
              Promover para Catalog
            </button>
            <button
              disabled={promoting}
              onClick={() => handlePromote("verified_inci")}
              className="rounded-lg bg-ink px-3 py-1.5 text-sm text-white hover:bg-ink/90 disabled:opacity-50"
            >
              Promover para Verified
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      {loading && <InlineLoading />}
      {error && <p className="text-coral">Erro: {error}</p>}
      {data && (
        <>
          <div className="overflow-x-auto rounded-lg border border-cream-dark bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-cream-dark text-left text-[10px] text-ink-muted uppercase tracking-wider">
                  <th className="w-10 px-3 py-3">
                    <input type="checkbox" onChange={toggleAll} checked={selected.size === data.items.length && data.items.length > 0} />
                  </th>
                  <th className="w-10 px-1 py-3"></th>
                  <th className="px-3 py-3">Produto</th>
                  <th className="px-3 py-3 w-24">Marca</th>
                  <th className="px-3 py-3 w-32">Motivo</th>
                  <th className="px-3 py-3">Detalhe</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <tr key={p.id} className="border-b border-cream-dark/50 hover:bg-cream/50 transition-colors">
                    <td className="px-3 py-2.5">
                      <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelect(p.id)} />
                    </td>
                    <td className="px-1 py-2.5">
                      {p.image_url_main ? (
                        <img src={p.image_url_main} alt="" className="h-8 w-8 rounded border border-cream-dark object-cover" />
                      ) : (
                        <div className="h-8 w-8 rounded border border-cream-dark bg-cream-dark/30" />
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <Link to={`/ops/products/${p.id}`} className="font-medium text-ink hover:underline">
                        {p.product_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-ink-muted">{p.brand_slug}</td>
                    <td className="px-3 py-2.5"><ReasonBadge code={p.rejection_code} /></td>
                    <td className="px-3 py-2.5 text-xs text-ink-muted truncate max-w-md" title={p.rejection_reason || ""}>
                      {p.rejection_reason || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between text-sm text-ink-muted">
            <span>{data.total} produtos em quarentena</span>
            <div className="flex gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                Anterior
              </button>
              <span className="flex items-center px-2 tabular-nums">Página {page}</span>
              <button onClick={() => setPage((p) => p + 1)} disabled={page * data.per_page >= data.total} className="rounded-lg border border-cream-dark px-3 py-1 hover:bg-cream disabled:opacity-50">
                Próxima
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
