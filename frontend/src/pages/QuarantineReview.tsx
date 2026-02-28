import { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { getQuarantine, approveQuarantine, rejectQuarantine } from '../lib/api';
import { useAPI } from '../hooks/useAPI';
import type { QuarantineItem } from '../types/api';
import StatusBadge from '../components/StatusBadge';
import LoadingState, { ErrorState, EmptyState } from '../components/LoadingState';

export default function QuarantineReview() {
  const [statusFilter, setStatusFilter] = useState('pending');
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  const fetcher = useCallback(
    () => getQuarantine(statusFilter || undefined),
    [statusFilter]
  );
  const { data: items, loading, error, refetch } = useAPI(fetcher, [statusFilter]);

  const stats = useMemo(() => {
    if (!items) return { pending: 0, approved: 0, rejected: 0, total: 0 };
    return {
      pending: items.filter((i) => i.review_status === 'pending').length,
      approved: items.filter((i) => i.review_status === 'approved').length,
      rejected: items.filter((i) => i.review_status === 'rejected').length,
      total: items.length,
    };
  }, [items]);

  async function handleApprove(id: string) {
    setActionInProgress(id);
    try {
      await approveQuarantine(id);
      refetch();
    } catch {
      // Error state handled by refetch
    } finally {
      setActionInProgress(null);
    }
  }

  async function handleReject(id: string) {
    setActionInProgress(id);
    try {
      await rejectQuarantine(id);
      refetch();
    } catch {
      // Error state handled by refetch
    } finally {
      setActionInProgress(null);
    }
  }

  if (loading) return <LoadingState message="Loading quarantine queue..." />;
  if (error) return <ErrorState message={error} onRetry={refetch} />;

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

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1 }}
        className="flex gap-4"
      >
        <div className="flex items-center gap-3 bg-amber-bg rounded-xl px-5 py-3">
          <div className="w-8 h-8 rounded-lg bg-amber/10 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-amber">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4" strokeLinecap="round" />
              <path d="M12 16h.01" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <p className="text-lg font-display font-semibold text-amber">{stats.pending}</p>
            <p className="text-[10px] uppercase tracking-wider text-amber/70">Pending Review</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-sage-bg rounded-xl px-5 py-3">
          <div className="w-8 h-8 rounded-lg bg-sage/10 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-sage">
              <path d="M20 6L9 17l-5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <p className="text-lg font-display font-semibold text-sage">{stats.approved}</p>
            <p className="text-[10px] uppercase tracking-wider text-sage/70">Approved</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-coral-bg rounded-xl px-5 py-3">
          <div className="w-8 h-8 rounded-lg bg-coral/10 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-coral">
              <path d="M18 6L6 18" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div>
            <p className="text-lg font-display font-semibold text-coral">{stats.rejected}</p>
            <p className="text-[10px] uppercase tracking-wider text-coral/70">Rejected</p>
          </div>
        </div>
        <div className="flex items-center gap-3 bg-white rounded-xl border border-ink/5 px-5 py-3">
          <div>
            <p className="text-lg font-display font-semibold text-ink-light">{stats.total}</p>
            <p className="text-[10px] uppercase tracking-wider text-ink-faint">Total Items</p>
          </div>
        </div>
      </motion.div>

      {/* Filter tabs */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="flex gap-1 bg-white rounded-xl border border-ink/5 p-1 w-fit"
      >
        {['pending', 'approved', 'rejected', ''].map((status) => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              statusFilter === status
                ? 'bg-champagne/10 text-champagne-dark shadow-sm'
                : 'text-ink-muted hover:text-ink'
            }`}
          >
            {status === '' ? 'All' : status === 'pending' ? 'Pending' : status === 'approved' ? 'Approved' : 'Rejected'}
          </button>
        ))}
      </motion.div>

      {/* Items list */}
      {!items || items.length === 0 ? (
        <EmptyState
          title="No quarantined items"
          description={statusFilter ? `No items with status "${statusFilter}".` : 'The quarantine queue is empty.'}
        />
      ) : (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4, delay: 0.25 }}
          className="space-y-3"
        >
          {items.map((item, i) => (
            <QuarantineCard
              key={item.id}
              item={item}
              index={i}
              expanded={expandedId === item.id}
              onToggle={() => setExpandedId(expandedId === item.id ? null : item.id)}
              onApprove={() => handleApprove(item.id)}
              onReject={() => handleReject(item.id)}
              busy={actionInProgress === item.id}
            />
          ))}
        </motion.div>
      )}
    </div>
  );
}

// ── Quarantine Card ──

function QuarantineCard({
  item,
  index,
  expanded,
  onToggle,
  onApprove,
  onReject,
  busy,
}: {
  item: QuarantineItem;
  index: number;
  expanded: boolean;
  onToggle: () => void;
  onApprove: () => void;
  onReject: () => void;
  busy: boolean;
}) {
  const rejectionCodes = item.rejection_code ? item.rejection_code.split(',').map((s) => s.trim()) : [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.3) }}
      className="bg-white rounded-xl border border-ink/5 shadow-sm overflow-hidden"
    >
      {/* Card Header */}
      <div
        onClick={onToggle}
        className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-cream/30 transition-colors"
      >
        {/* Severity indicator */}
        <div className={`w-1 h-10 rounded-full flex-shrink-0 ${
          item.review_status === 'approved' ? 'bg-sage' : item.review_status === 'rejected' ? 'bg-ink-faint' : 'bg-coral'
        }`} />

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-ink truncate">{item.product_name}</h3>
            <StatusBadge status={item.review_status} />
          </div>
          <div className="flex items-center gap-3 mt-1">
            <span className="text-xs text-ink-muted">{item.brand_slug}</span>
            <span className="text-xs text-ink-faint">&middot;</span>
            <span className="text-xs text-coral">{item.rejection_reason}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {item.review_status === 'pending' && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onReject();
                }}
                disabled={busy}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-coral/10 text-coral rounded-lg text-xs font-medium hover:bg-coral/20 transition-colors disabled:opacity-50"
              >
                {busy ? (
                  <motion.div
                    className="w-3 h-3 rounded-full border-2 border-coral/30 border-t-coral"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  />
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M18 6L6 18" />
                    <path d="M6 6l12 12" />
                  </svg>
                )}
                Reject
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onApprove();
                }}
                disabled={busy}
                className="flex items-center gap-1.5 px-3.5 py-2 bg-sage text-white rounded-lg text-xs font-medium hover:bg-sage/90 transition-colors disabled:opacity-50"
              >
                {busy ? (
                  <motion.div
                    className="w-3 h-3 rounded-full border-2 border-white/30 border-t-white"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  />
                ) : (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                )}
                Approve
              </button>
            </>
          )}

          {/* Expand chevron */}
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="text-ink-faint"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </motion.div>
        </div>
      </div>

      {/* Expanded Details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 pt-1 border-t border-ink/5 space-y-4">
              {/* Rejection Reason */}
              <div>
                <h4 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                  Rejection Reason
                </h4>
                <p className="text-sm text-ink-light">{item.rejection_reason}</p>
              </div>

              {/* Rejection Codes */}
              {rejectionCodes.length > 0 && (
                <div>
                  <h4 className="text-[11px] uppercase tracking-wider text-ink-muted font-semibold mb-2">
                    Failed Checks
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {rejectionCodes.map((code) => (
                      <span
                        key={code}
                        className="px-2.5 py-1 bg-coral-bg rounded-lg text-xs text-coral font-medium"
                      >
                        {code}
                      </span>
                    ))}
                  </div>
                </div>
              )}

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
                    className="text-sm text-champagne-dark hover:underline break-all"
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
                  <p className="text-sm text-ink-light">{item.reviewer_notes}</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
