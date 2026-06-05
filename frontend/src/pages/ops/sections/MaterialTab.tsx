/**
 * Aba "Material" — upload/preview/delete dos documentos da KB da Moon.
 * Conteúdo migrado quase 1:1 da versão antiga de OpsKnowledge.tsx; única
 * diferença funcional é aceitar `.md` (Compêndio).
 */
import { useCallback, useEffect, useState } from 'react';
import { Upload, Trash2, RefreshCw, Eye, AlertCircle } from 'lucide-react';
import {
  listKnowledge, uploadKnowledge, deleteKnowledge, readKnowledge,
  type KnowledgeList, type KnowledgeChunkSummary,
} from '@/lib/ops-api';

function fmtBytes(n: number) {
  if (n < 1024) return `${n} chars`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

function fmtDate(s: string | null) {
  if (!s) return '—';
  try { return new Date(s).toLocaleString('pt-BR'); } catch { return s; }
}

export default function MaterialTab() {
  const [data, setData] = useState<KnowledgeList | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [preview, setPreview] = useState<{ source: string; content: string } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true); setError(null);
    try { setData(await listKnowledge()); }
    catch (e) { setError(e instanceof Error ? e.message : 'Erro ao carregar'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  async function handleFiles(files: FileList | File[]) {
    setUploading(true); setError(null);
    const list = Array.from(files);
    try {
      for (const file of list) {
        if (!/\.(docx|pdf|md|markdown)$/i.test(file.name)) {
          throw new Error(`${file.name}: só .docx, .pdf ou .md`);
        }
        await uploadKnowledge(file);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erro no upload');
    } finally { setUploading(false); }
  }

  async function onDrop(e: React.DragEvent) {
    e.preventDefault(); setDragOver(false);
    if (e.dataTransfer.files.length) await handleFiles(e.dataTransfer.files);
  }

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) await handleFiles(e.target.files);
    e.target.value = '';
  }

  async function onDelete(c: KnowledgeChunkSummary) {
    if (!confirm(`Remover "${c.source}" do conteúdo proprietário?\n(reversível — basta reupload).`)) return;
    setError(null);
    try { await deleteKnowledge(c.source); await refresh(); }
    catch (e) { setError(e instanceof Error ? e.message : 'Erro ao remover'); }
  }

  async function onPreview(c: KnowledgeChunkSummary) {
    try { const full = await readKnowledge(c.source); setPreview({ source: c.source, content: full.content }); }
    catch (e) { setError(e instanceof Error ? e.message : 'Erro ao ler conteúdo'); }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-semibold text-ink">Documentos proprietários</h2>
          <p className="text-sm text-ink-muted mt-1 max-w-xl">
            Material consultado pela Moon a cada resposta. Aceita <code className="text-ink">.docx</code>,{' '}
            <code className="text-ink">.pdf</code> e <code className="text-ink">.md</code>.
          </p>
        </div>
        <button onClick={refresh} disabled={loading}
          className="p-2 rounded-lg border border-cream-dark text-ink-muted hover:text-ink hover:border-ink disabled:opacity-40">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {data && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint">Fontes</div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">{data.total_sources}</div>
          </div>
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint">Tamanho</div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">{fmtBytes(data.total_chars)}</div>
          </div>
          <div className="rounded-xl border border-cream-dark bg-white p-4">
            <div className="text-xs uppercase tracking-wide text-ink-faint">~ Tokens</div>
            <div className="text-3xl font-display font-semibold text-ink mt-1">{data.total_tokens_estimate.toLocaleString('pt-BR')}</div>
            <div className="text-[11px] text-ink-faint mt-1">contexto Claude: 200k</div>
          </div>
        </div>
      )}

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`rounded-2xl border-2 border-dashed p-8 text-center transition-colors ${
          dragOver ? 'border-[#ff5900] bg-[#ff5900]/5'
          : uploading ? 'border-cream-dark bg-cream/40'
          : 'border-cream-dark bg-white hover:border-ink'}`}>
        <Upload size={32} className="mx-auto text-ink-muted mb-2" />
        <p className="text-sm text-ink">
          {uploading ? 'Enviando…' : 'Arraste .docx, .pdf ou .md aqui ou'}{' '}
          {!uploading && (
            <label className="text-[#ff5900] underline cursor-pointer">
              escolha um arquivo
              <input type="file" className="hidden" accept=".docx,.pdf,.md,.markdown" multiple onChange={onPick} />
            </label>
          )}
        </p>
        <p className="text-xs text-ink-faint mt-1">
          Existente com mesmo nome será substituído. Moon recarrega automaticamente.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-start gap-2">
          <AlertCircle size={16} className="shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      <div className="rounded-2xl border border-cream-dark bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-cream/50 text-ink-muted text-xs uppercase">
            <tr>
              <th className="text-left px-4 py-3">Fonte</th>
              <th className="text-right px-4 py-3">Tamanho</th>
              <th className="text-right px-4 py-3">~ Tokens</th>
              <th className="text-left px-4 py-3">Atualizado</th>
              <th className="px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {data?.chunks.length === 0 && (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-ink-faint">
                Nenhum documento ainda. Suba um arquivo acima.
              </td></tr>
            )}
            {data?.chunks.map((c) => (
              <tr key={c.source} className="border-t border-cream-dark">
                <td className="px-4 py-3 text-ink font-medium">{c.source}</td>
                <td className="px-4 py-3 text-right text-ink-muted">{fmtBytes(c.char_count)}</td>
                <td className="px-4 py-3 text-right text-ink-muted">{c.token_estimate.toLocaleString('pt-BR')}</td>
                <td className="px-4 py-3 text-ink-muted">{fmtDate(c.updated_at)}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 justify-end">
                    <button onClick={() => onPreview(c)} title="Ver conteúdo"
                      className="p-1.5 rounded-md text-ink-muted hover:text-ink hover:bg-cream">
                      <Eye size={14} />
                    </button>
                    <button onClick={() => onDelete(c)} title="Remover"
                      className="p-1.5 rounded-md text-ink-muted hover:text-red-600 hover:bg-red-50">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {preview && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
             onClick={() => setPreview(null)}>
          <div className="bg-white rounded-2xl max-w-3xl w-full max-h-[80vh] flex flex-col"
               onClick={(e) => e.stopPropagation()}>
            <div className="px-5 py-3 border-b border-cream-dark flex items-center justify-between">
              <h2 className="font-medium text-ink">{preview.source}</h2>
              <button onClick={() => setPreview(null)} className="text-ink-muted hover:text-ink">✕</button>
            </div>
            <pre className="flex-1 overflow-auto p-5 text-xs text-ink whitespace-pre-wrap font-mono">
              {preview.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
