import { useState } from 'react';
import { useAPI } from '../hooks/useAPI';
import { fetchReviewQueue, resolveReviewItem } from '../lib/api';
import type { ReviewQueueItem } from '../types/api';

export default function ReviewQueue() {
  const [filter, setFilter] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const { data: items, loading, error, refetch } = useAPI<ReviewQueueItem[]>(
    () => fetchReviewQueue(filter),
    [filter],
  );

  const handleResolve = async (itemId: string, status: string) => {
    await resolveReviewItem(itemId, status);
    refetch();
  };

  if (loading) return <div className="p-6">Loading review queue...</div>;
  if (error) return <div className="p-6 text-red-500">Error: {error}</div>;

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Review Queue</h1>
        <div className="flex gap-2">
          {(['pending', 'approved', 'rejected'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1 rounded text-sm ${
                filter === s ? 'bg-zinc-900 text-white' : 'bg-zinc-100 text-zinc-700'
              }`}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {!items?.length ? (
        <p className="text-zinc-500">No {filter} items in the review queue.</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">{item.product_name}</span>
                  <span className="text-zinc-500 text-sm ml-2">{item.brand_slug}</span>
                </div>
                <span className="text-xs px-2 py-1 rounded bg-zinc-100">{item.field_name}</span>
              </div>

              {item.comparison && (
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <div className="text-zinc-500 text-xs mb-1">Pass 1</div>
                    <div className="bg-zinc-50 p-2 rounded font-mono text-xs break-all">
                      {item.comparison.pass_1_value || '(empty)'}
                    </div>
                  </div>
                  <div>
                    <div className="text-zinc-500 text-xs mb-1">Pass 2</div>
                    <div className="bg-zinc-50 p-2 rounded font-mono text-xs break-all">
                      {item.comparison.pass_2_value || '(empty)'}
                    </div>
                  </div>
                </div>
              )}

              {item.status === 'pending' && (
                <div className="flex gap-2 pt-2">
                  <button
                    onClick={() => handleResolve(item.id, 'approved')}
                    className="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700"
                  >
                    Approve
                  </button>
                  <button
                    onClick={() => handleResolve(item.id, 'rejected')}
                    className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700"
                  >
                    Reject
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
