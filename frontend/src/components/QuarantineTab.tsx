import { useState, useCallback, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useAPI } from '@/hooks/useAPI';
import { getQuarantineByBrand, approveQuarantine, rejectQuarantine } from '@/lib/api';
import type { QuarantineItem } from '@/types/api';
import SessionProgress from '@/components/SessionProgress';

interface QuarantineTabProps {
  brandSlug: string;
  onCountChange?: (count: number) => void;
}

export default function QuarantineTab({ brandSlug, onCountChange }: QuarantineTabProps) {
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());
  const [confirmingReject, setConfirmingReject] = useState<string | null>(null);

  const fetcher = useCallback(() => getQuarantineByBrand(brandSlug), [brandSlug]);
  const { data: items, loading, error, refetch } = useAPI(fetcher, [brandSlug]);

  const visibleItems = useMemo(
    () => items?.filter((item) => !removedIds.has(item.id)) ?? [],
    [items, removedIds]
  );

  const totalItems = items?.length ?? 0;
  const reviewedCount = removedIds.size;

  async function handleApprove(item: QuarantineItem) {
    try {
      await approveQuarantine(item.id);
      setRemovedIds((prev) => new Set(prev).add(item.id));
      onCountChange?.(totalItems - removedIds.size - 1);
      toast.success(`${item.product_name ?? 'Produto'} aprovado — ${visibleItems.length - 1} restantes em quarentena`);
    } catch {
      toast.error('Falha ao aprovar produto');
    }
  }

  async function handleReject(item: QuarantineItem) {
    if (confirmingReject !== item.id) {
      setConfirmingReject(item.id);
      return;
    }
    try {
      await rejectQuarantine(item.id);
      setRemovedIds((prev) => new Set(prev).add(item.id));
      setConfirmingReject(null);
      onCountChange?.(totalItems - removedIds.size - 1);
      toast.success(`${item.product_name ?? 'Produto'} rejeitado`);
    } catch {
      toast.error('Falha ao rejeitar produto');
    }
  }

  if (loading) {
    return (
      <div className="space-y-3 py-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-16 rounded-lg bg-ink/5 animate-pulse" />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <p className="text-sm text-coral mb-3">{error}</p>
        <Button variant="outline" size="sm" onClick={refetch}>Tentar novamente</Button>
      </div>
    );
  }

  if (totalItems === 0) {
    return (
      <div className="text-center py-12">
        <svg className="mx-auto mb-3 text-emerald-500" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
        <p className="text-sm text-ink-muted">Nenhum produto em quarentena</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 py-2">
      <SessionProgress reviewed={reviewedCount} total={totalItems} />

      <AnimatePresence mode="popLayout">
        {visibleItems.map((item) => {
          const rejectionCodes = item.rejection_code
            ? item.rejection_code.split(',').map((s) => s.trim())
            : [];

          return (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: 40, transition: { duration: 0.25 } }}
              className="flex items-center gap-3 p-3 rounded-lg border border-ink/5 bg-white"
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink truncate">
                  {item.product_name ?? 'Produto desconhecido'}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="destructive" className="text-[10px] h-4 px-1.5">
                    {item.rejection_reason}
                  </Badge>
                  {rejectionCodes.map((code) => (
                    <Badge key={code} variant="outline" className="text-[10px] h-4 px-1.5 text-coral border-coral/30">
                      {code}
                    </Badge>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 text-xs"
                  onClick={() => handleApprove(item)}
                >
                  Aprovar
                </Button>
                <Button
                  size="sm"
                  variant={confirmingReject === item.id ? 'destructive' : 'outline'}
                  className="h-7 text-xs"
                  onClick={() => handleReject(item)}
                  onBlur={() => setConfirmingReject(null)}
                >
                  {confirmingReject === item.id ? 'Confirmar' : 'Rejeitar'}
                </Button>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
