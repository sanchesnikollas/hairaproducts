import { useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import { getQuarantine, approveQuarantine, rejectQuarantine } from '@/lib/api';
import { useAPI } from '@/hooks/useAPI';
import type { QuarantineItem } from '@/types/api';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

type ReviewStatus = 'pending' | 'approved' | 'rejected';

export default function QuarantineReview() {
  const [activeTab, setActiveTab] = useState<ReviewStatus>('pending');
  const [removedIds, setRemovedIds] = useState<Set<string>>(new Set());

  const fetcher = useCallback(() => getQuarantine(activeTab), [activeTab]);
  const { data: items, loading, error, refetch } = useAPI(fetcher, [activeTab]);

  const visibleItems = items?.filter((item) => !removedIds.has(item.id)) ?? [];

  const counts = {
    pending: items?.filter((i) => i.review_status === 'pending').length ?? 0,
    approved: items?.filter((i) => i.review_status === 'approved').length ?? 0,
    rejected: items?.filter((i) => i.review_status === 'rejected').length ?? 0,
  };

  function handleTabChange(value: string | number | null) {
    if (value && typeof value === 'string') {
      setActiveTab(value as ReviewStatus);
      setRemovedIds(new Set());
    }
  }

  async function handleApprove(id: string, notes: string) {
    try {
      await approveQuarantine(id, notes || undefined);
      setRemovedIds((prev) => new Set(prev).add(id));
      toast.success('Item approved successfully');
      setTimeout(() => refetch(), 600);
    } catch {
      toast.error('Failed to approve item');
    }
  }

  async function handleReject(id: string, notes: string) {
    try {
      await rejectQuarantine(id, notes || undefined);
      setRemovedIds((prev) => new Set(prev).add(id));
      toast.success('Item rejected');
      setTimeout(() => refetch(), 600);
    } catch {
      toast.error('Failed to reject item');
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
          Quarantine Review
        </h1>
        <p className="mt-2 text-sm text-ink-muted">
          Review quarantined products and approve or reject with evidence trail.
        </p>
      </motion.div>

      {/* Tabs */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
      >
        <Tabs value={activeTab} onValueChange={handleTabChange}>
          <TabsList>
            <TabsTrigger value="pending" className="gap-2">
              Pending
              <Badge variant="outline" className="ml-1 text-[10px] px-1.5 h-4">
                {counts.pending}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="approved" className="gap-2">
              Approved
              <Badge variant="outline" className="ml-1 text-[10px] px-1.5 h-4">
                {counts.approved}
              </Badge>
            </TabsTrigger>
            <TabsTrigger value="rejected" className="gap-2">
              Rejected
              <Badge variant="outline" className="ml-1 text-[10px] px-1.5 h-4">
                {counts.rejected}
              </Badge>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pending">
            <ItemList
              items={visibleItems}
              loading={loading}
              error={error}
              onApprove={handleApprove}
              onReject={handleReject}
              onRetry={refetch}
              isPending
            />
          </TabsContent>
          <TabsContent value="approved">
            <ItemList
              items={visibleItems}
              loading={loading}
              error={error}
              onApprove={handleApprove}
              onReject={handleReject}
              onRetry={refetch}
            />
          </TabsContent>
          <TabsContent value="rejected">
            <ItemList
              items={visibleItems}
              loading={loading}
              error={error}
              onApprove={handleApprove}
              onReject={handleReject}
              onRetry={refetch}
            />
          </TabsContent>
        </Tabs>
      </motion.div>
    </div>
  );
}

// ── Item List ──

function ItemList({
  items,
  loading,
  error,
  onApprove,
  onReject,
  onRetry,
  isPending = false,
}: {
  items: QuarantineItem[];
  loading: boolean;
  error: string | null;
  onApprove: (id: string, notes: string) => void;
  onReject: (id: string, notes: string) => void;
  onRetry: () => void;
  isPending?: boolean;
}) {
  if (loading) {
    return (
      <div className="space-y-4 mt-4">
        {[0, 1, 2].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="mt-8 text-center">
        <p className="text-sm text-coral mb-3">{error}</p>
        <Button variant="outline" onClick={onRetry}>
          Retry
        </Button>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="mt-12 text-center">
        <p className="text-sm text-ink-muted">No items in this category</p>
      </div>
    );
  }

  return (
    <div className="space-y-4 mt-4">
      <AnimatePresence mode="popLayout">
        {items.map((item, i) => (
          <QuarantineCard
            key={item.id}
            item={item}
            index={i}
            onApprove={onApprove}
            onReject={onReject}
            isPending={isPending}
          />
        ))}
      </AnimatePresence>
    </div>
  );
}

// ── Skeleton Card ──

function SkeletonCard() {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-3">
          <Skeleton className="h-5 w-48" />
          <Skeleton className="h-5 w-16 rounded-full" />
        </div>
        <div className="flex items-center gap-2 mt-1">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
        </div>
      </CardHeader>
      <CardContent>
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4 mt-2" />
      </CardContent>
    </Card>
  );
}

// ── Quarantine Card ──

function QuarantineCard({
  item,
  index,
  onApprove,
  onReject,
  isPending,
}: {
  item: QuarantineItem;
  index: number;
  onApprove: (id: string, notes: string) => void;
  onReject: (id: string, notes: string) => void;
  isPending: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const rejectionCodes = item.rejection_code
    ? item.rejection_code.split(',').map((s) => s.trim())
    : [];

  async function handleAction(action: 'approve' | 'reject') {
    setBusy(true);
    try {
      if (action === 'approve') {
        await onApprove(item.id, notes);
      } else {
        await onReject(item.id, notes);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, x: -24, transition: { duration: 0.3 } }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.04, 0.3) }}
    >
      <Card className="overflow-hidden">
        {/* Card Header — clickable to expand */}
        <CardHeader
          className="cursor-pointer select-none"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 min-w-0">
              <CardTitle className="truncate text-ink font-semibold">
                {item.product_name ?? 'Unknown Product'}
              </CardTitle>
              <Badge variant="destructive">{item.rejection_reason}</Badge>
            </div>
            <motion.svg
              animate={{ rotate: expanded ? 180 : 0 }}
              transition={{ duration: 0.2 }}
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-ink-muted shrink-0"
            >
              <path d="M6 9l6 6 6-6" />
            </motion.svg>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-ink-muted">{item.brand_slug}</span>
            {rejectionCodes.length > 0 && (
              <>
                <span className="text-xs text-ink-muted">&middot;</span>
                <div className="flex flex-wrap gap-1">
                  {rejectionCodes.map((code) => (
                    <Badge
                      key={code}
                      variant="outline"
                      className="text-[10px] h-4 px-1.5 text-coral border-coral/30"
                    >
                      {code}
                    </Badge>
                  ))}
                </div>
              </>
            )}
          </div>
        </CardHeader>

        {/* Expandable details */}
        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25 }}
              className="overflow-hidden"
            >
              <CardContent className="space-y-4 border-t border-ink/5 pt-4">
                {/* Rejection Reason */}
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-1">
                    Rejection Reason
                  </h4>
                  <p className="text-sm text-ink">{item.rejection_reason}</p>
                </div>

                {/* Product URL */}
                {item.product_url && (
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-1">
                      Product URL
                    </h4>
                    <a
                      href={item.product_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-champagne hover:underline break-all"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {item.product_url}
                    </a>
                  </div>
                )}

                {/* Reviewer Notes */}
                {item.reviewer_notes && (
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-1">
                      Reviewer Notes
                    </h4>
                    <p className="text-sm text-ink">{item.reviewer_notes}</p>
                  </div>
                )}
              </CardContent>

              {/* Actions — only for pending items */}
              {isPending && (
                <CardFooter className="gap-3">
                  <Input
                    placeholder="Reviewer notes (optional)"
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="flex-1"
                    onClick={(e) => e.stopPropagation()}
                  />
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAction('approve');
                    }}
                  >
                    {busy ? 'Processing...' : 'Approve'}
                  </Button>
                  <Button
                    variant="destructive"
                    disabled={busy}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleAction('reject');
                    }}
                  >
                    {busy ? 'Processing...' : 'Reject'}
                  </Button>
                </CardFooter>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </Card>
    </motion.div>
  );
}
