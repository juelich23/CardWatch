'use client';

import { useQuery } from '@apollo/client/react';
import { GET_PRICE_HISTORY } from '@/lib/graphql/queries';

interface PriceSnapshot {
  snapshotDate: string;
  currentBid: number | null;
  bidCount: number;
  status: string;
}

interface PriceHistoryChartProps {
  itemId: number;
  days?: number;
}

export function PriceHistoryChart({ itemId, days = 14 }: PriceHistoryChartProps) {
  const { data, loading, error } = useQuery<{ priceHistory: PriceSnapshot[] }>(GET_PRICE_HISTORY, {
    variables: { itemId, days },
    fetchPolicy: 'cache-first',
  });

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  if (loading) {
    return (
      <div className="space-y-3 animate-pulse">
        <div className="flex justify-between">
          <div className="h-4 w-20 bg-panel-2 rounded" />
          <div className="h-4 w-20 bg-panel-2 rounded" />
          <div className="h-4 w-24 bg-panel-2 rounded" />
        </div>
        <div className="h-24 flex items-end gap-1">
          {Array.from({ length: 14 }).map((_, i) => (
            <div key={i} className="flex-1 bg-panel-2 rounded-t" style={{ height: `${30 + Math.random() * 70}%` }} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-red-400 text-sm py-2">
        Error loading price history
      </div>
    );
  }

  const snapshots: PriceSnapshot[] = data?.priceHistory || [];

  if (snapshots.length === 0) {
    return (
      <div className="text-text-2 text-sm py-4 text-center">
        No price history available yet.
        <p className="text-xs mt-1">History is recorded daily.</p>
      </div>
    );
  }

  // Calculate min/max for chart scaling
  const bids = snapshots.map(s => s.currentBid || 0).filter(b => b > 0);
  const minBid = bids.length > 0 ? Math.min(...bids) : 0;
  const maxBid = bids.length > 0 ? Math.max(...bids) : 0;
  const range = maxBid - minBid || 1;

  // Calculate price change
  const firstBid = snapshots[0]?.currentBid || 0;
  const lastBid = snapshots[snapshots.length - 1]?.currentBid || 0;
  const priceChange = lastBid - firstBid;
  const priceChangePercent = firstBid > 0 ? ((priceChange / firstBid) * 100).toFixed(1) : '0';

  return (
    <div className="space-y-3">
      {/* Summary stats */}
      <div className="flex justify-between text-sm">
        <div>
          <span className="text-text-2">Start:</span>{' '}
          <span className="text-text font-medium">{formatCurrency(firstBid)}</span>
        </div>
        <div>
          <span className="text-text-2">Current:</span>{' '}
          <span className="text-text font-medium">{formatCurrency(lastBid)}</span>
        </div>
        <div>
          <span className="text-text-2">Change:</span>{' '}
          <span className={`font-medium ${priceChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {priceChange >= 0 ? '+' : ''}{formatCurrency(priceChange)} ({priceChange >= 0 ? '+' : ''}{priceChangePercent}%)
          </span>
        </div>
      </div>

      {/* Simple bar chart */}
      <div className="h-24 flex items-end gap-1">
        {snapshots.map((snapshot, index) => {
          const bid = snapshot.currentBid || 0;
          const height = bid > 0 ? Math.max(8, ((bid - minBid) / range) * 100) : 0;

          return (
            <div
              key={snapshot.snapshotDate}
              className="flex-1 group relative"
            >
              {/* Bar */}
              <div
                className="w-full bg-accent/60 hover:bg-accent rounded-t transition-colors"
                style={{ height: `${height}%` }}
              ></div>

              {/* Tooltip */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                <div className="bg-panel border border-border rounded px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                  <div className="text-text font-medium">{formatCurrency(bid)}</div>
                  <div className="text-text-2">{formatDate(snapshot.snapshotDate)}</div>
                  <div className="text-text-2">{snapshot.bidCount} bids</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* X-axis labels */}
      <div className="flex justify-between text-xs text-text-2">
        <span>{formatDate(snapshots[0]?.snapshotDate || '')}</span>
        <span>{formatDate(snapshots[snapshots.length - 1]?.snapshotDate || '')}</span>
      </div>

      {/* Bid history table */}
      {snapshots.length > 1 && (
        <div className="mt-4 max-h-32 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="sticky top-0 bg-panel">
              <tr className="text-text-2 border-b border-border">
                <th className="text-left py-1">Date</th>
                <th className="text-right py-1">Bid</th>
                <th className="text-right py-1"># Bids</th>
                <th className="text-right py-1">Change</th>
              </tr>
            </thead>
            <tbody>
              {[...snapshots].reverse().map((snapshot, index, arr) => {
                const prevSnapshot = arr[index + 1];
                const change = prevSnapshot
                  ? (snapshot.currentBid || 0) - (prevSnapshot.currentBid || 0)
                  : 0;

                return (
                  <tr key={snapshot.snapshotDate} className="border-b border-border/50">
                    <td className="py-1 text-text">{formatDate(snapshot.snapshotDate)}</td>
                    <td className="py-1 text-right text-text">{formatCurrency(snapshot.currentBid || 0)}</td>
                    <td className="py-1 text-right text-text-2">{snapshot.bidCount}</td>
                    <td className={`py-1 text-right ${change > 0 ? 'text-green-400' : change < 0 ? 'text-red-400' : 'text-text-2'}`}>
                      {change !== 0 && (change > 0 ? '+' : '')}{change !== 0 ? formatCurrency(change) : '-'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
