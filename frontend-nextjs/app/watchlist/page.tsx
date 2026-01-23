'use client';

import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@apollo/client/react';
import { useAuth } from '@/lib/providers/AuthProvider';
import { GET_WATCHLIST, TOGGLE_WATCH } from '@/lib/graphql/queries';
import { AuctionCard } from '@/components/AuctionCard';
import { AuctionGridSkeleton } from '@/components/AuctionCardSkeleton';
import { AuctionItem } from '@/lib/types';

export default function WatchlistPage() {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);
  const [includeEnded, setIncludeEnded] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, loading, error, refetch } = useQuery<{
    watchlist: { items: AuctionItem[]; total: number; hasMore: boolean };
  }>(GET_WATCHLIST, {
    variables: { includeEnded, page, pageSize },
    skip: !user,
    fetchPolicy: 'cache-and-network',
    nextFetchPolicy: 'cache-first',
  });

  const [toggleWatch] = useMutation(TOGGLE_WATCH, {
    onCompleted: () => {
      refetch();
    },
  });

  const handleRemoveFromWatchlist = async (itemId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    await toggleWatch({ variables: { itemId } });
  };

  const items: AuctionItem[] = data?.watchlist?.items || [];
  const total = data?.watchlist?.total || 0;
  const hasMore = data?.watchlist?.hasMore || false;

  const formatTimeRemaining = (endTime?: string) => {
    if (!endTime) return 'Unknown';
    const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
    const end = new Date(utcEndTime);
    const now = new Date();
    const diff = end.getTime() - now.getTime();

    if (diff < 0) return 'Ended';

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const isEnded = (endTime?: string) => {
    if (!endTime) return false;
    const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
    return new Date(utcEndTime).getTime() < Date.now();
  };

  // Show minimal loading during SSR/hydration, then show content
  if (!mounted) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-2xl font-bold text-text mb-6">My Watchlist</h1>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-2xl font-bold text-text mb-6">My Watchlist</h1>
          <div className="bg-panel border border-border rounded-lg p-8 text-center">
            <svg
              className="w-12 h-12 text-text-2 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
              />
            </svg>
            <p className="text-text-2 mb-4">Please sign in to view your watchlist.</p>
            <p className="text-text-2 text-sm">
              Create an account to save items and track auctions across all platforms.
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-background">
        <div className="container mx-auto px-4 py-8">
          <h1 className="text-2xl font-bold text-text mb-6">My Watchlist</h1>
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
            <p className="text-red-400">Error loading watchlist: {error.message}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-text">My Watchlist</h1>
            <p className="text-text-2 text-sm mt-1">
              {total} {total === 1 ? 'item' : 'items'} saved
            </p>
          </div>

          {/* Include ended toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeEnded}
              onChange={(e) => {
                setIncludeEnded(e.target.checked);
                setPage(1);
              }}
              className="w-4 h-4 rounded border-border bg-panel text-accent focus:ring-accent focus:ring-offset-0"
            />
            <span className="text-text-2 text-sm">Show ended auctions</span>
          </label>
        </div>

        {loading && items.length === 0 ? (
          <AuctionGridSkeleton count={8} />
        ) : items.length === 0 ? (
          <div className="bg-panel border border-border rounded-lg p-8 text-center">
            <svg
              className="w-12 h-12 text-text-2 mx-auto mb-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
              />
            </svg>
            <p className="text-text-2 mb-2">Your watchlist is empty</p>
            <p className="text-text-2 text-sm">
              Browse auctions and click the heart icon to add items to your watchlist.
            </p>
            <a
              href="/"
              className="inline-block mt-4 px-4 py-2 bg-accent hover:bg-accent/80 text-white text-sm font-medium rounded-md transition-colors"
            >
              Browse Auctions
            </a>
          </div>
        ) : (
          <>
            {/* Items grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {items.map((item) => (
                <div key={item.id} className="relative">
                  {/* Ended overlay */}
                  {isEnded(item.endTime) && (
                    <div className="absolute inset-0 bg-background/70 z-10 flex items-center justify-center rounded-lg">
                      <span className="bg-red-500/20 text-red-400 border border-red-500/30 px-3 py-1 rounded-full text-sm font-medium">
                        Auction Ended
                      </span>
                    </div>
                  )}

                  {/* Remove button */}
                  <button
                    onClick={(e) => handleRemoveFromWatchlist(item.id, e)}
                    className="absolute top-2 right-12 z-20 w-8 h-8 bg-panel/90 hover:bg-red-500/20 border border-border hover:border-red-500/30 rounded-full flex items-center justify-center transition-colors group"
                    title="Remove from watchlist"
                  >
                    <svg
                      className="w-4 h-4 text-text-2 group-hover:text-red-400"
                      fill="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                    </svg>
                  </button>

                  <AuctionCard item={item} />
                </div>
              ))}
            </div>

            {/* Pagination */}
            {(page > 1 || hasMore) && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 bg-panel border border-border rounded-md text-text-2 hover:text-text hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <span className="px-4 py-2 text-text-2">
                  Page {page} of {Math.ceil(total / pageSize)}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={!hasMore}
                  className="px-4 py-2 bg-panel border border-border rounded-md text-text-2 hover:text-text hover:border-accent disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
