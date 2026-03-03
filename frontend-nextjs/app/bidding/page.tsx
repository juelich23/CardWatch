'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useQuery } from '@apollo/client/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { biddingAPI } from '@/lib/api/bidding';
import { GET_AUCTION_ITEMS } from '@/lib/graphql/queries';
import { useAuth } from '@/lib/providers/AuthProvider';
import type { AuctionItem } from '@/lib/types';
import type { SnipeStats, GixenSnipe } from '@/lib/types/bidding';
import { formatCurrency, formatTimeRemaining, isEndingSoon, statusColor } from '@/lib/formatters';
import { Clock } from 'lucide-react';

const PAGE_SIZE = 24;

export default function BiddingDashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState<SnipeStats | null>(null);
  const [recentSnipes, setRecentSnipes] = useState<GixenSnipe[]>([]);
  const [snipedItemIds, setSnipedItemIds] = useState<Set<string>>(new Set());
  const [statsLoading, setStatsLoading] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  // Search / filter state
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sortBy, setSortBy] = useState('end_time');
  const [sport, setSport] = useState('');
  const [page, setPage] = useState(1);

  // Snipe dialog state
  const [snipeItem, setSnipeItem] = useState<AuctionItem | null>(null);
  const [maxBid, setMaxBid] = useState('');
  const [bidOffset, setBidOffset] = useState(6);
  const [snipeLoading, setSnipeLoading] = useState(false);
  const [snipeError, setSnipeError] = useState<string | null>(null);
  const [snipeSuccess, setSnipeSuccess] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Load stats + recent snipes
  const loadStats = useCallback(async () => {
    if (!user) {
      setStatsLoading(false);
      return;
    }
    try {
      const [s, snipes, allActive] = await Promise.all([
        biddingAPI.getSnipeStats(),
        biddingAPI.listSnipes({ limit: 5 }),
        biddingAPI.listSnipes({ limit: 200 }),
      ]);
      setStats(s);
      setRecentSnipes(snipes);
      // Track which items already have snipes (by DB item_id)
      const ids = new Set(allActive.map((sn: GixenSnipe) => String(sn.item_id)));
      setSnipedItemIds(ids);
      setStatsError(null);
    } catch (err: unknown) {
      setStatsError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setStatsLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  // GraphQL query for eBay items
  const { data, loading: itemsLoading, fetchMore } = useQuery<{
    auctionItems: { items: AuctionItem[]; total: number; hasMore: boolean };
  }>(GET_AUCTION_ITEMS, {
    variables: {
      page: 1,
      pageSize: PAGE_SIZE,
      auctionHouse: 'ebay',
      status: 'Live',
      sortBy,
      search: debouncedSearch || undefined,
      sport: sport || undefined,
    },
    fetchPolicy: 'cache-and-network',
  });

  const items: AuctionItem[] = data?.auctionItems?.items || [];
  const hasMore = data?.auctionItems?.hasMore || false;
  const total = data?.auctionItems?.total || 0;

  const loadMore = () => {
    const nextPage = page + 1;
    setPage(nextPage);
    fetchMore({
      variables: { page: nextPage },
      updateQuery: (prev, { fetchMoreResult }) => {
        if (!fetchMoreResult) return prev;
        return {
          auctionItems: {
            ...fetchMoreResult.auctionItems,
            items: [
              ...prev.auctionItems.items,
              ...fetchMoreResult.auctionItems.items,
            ],
          },
        };
      },
    });
  };

  // Snipe submission
  const handleSnipe = async () => {
    if (!snipeItem || !maxBid) return;
    const bidAmount = parseFloat(maxBid);
    if (isNaN(bidAmount) || bidAmount <= 0) {
      setSnipeError('Enter a valid bid amount');
      return;
    }

    setSnipeLoading(true);
    setSnipeError(null);
    try {
      await biddingAPI.createSnipe(snipeItem.id, bidAmount, bidOffset);
      setSnipeSuccess(`Snipe set for $${bidAmount.toFixed(2)}`);
      setSnipedItemIds(prev => new Set([...prev, String(snipeItem.id)]));
      // Refresh stats
      loadStats();
      // Close dialog after brief delay
      setTimeout(() => {
        setSnipeItem(null);
        setSnipeSuccess(null);
        setMaxBid('');
      }, 1200);
    } catch (err: unknown) {
      setSnipeError(err instanceof Error ? err.message : 'Failed to create snipe');
    } finally {
      setSnipeLoading(false);
    }
  };

  const openSnipeDialog = (item: AuctionItem) => {
    setSnipeItem(item);
    setMaxBid(item.currentBid ? (item.currentBid + 1).toFixed(2) : '');
    setBidOffset(6);
    setSnipeError(null);
    setSnipeSuccess(null);
  };

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-text mb-6">Bidding</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-text-2">Please sign in to access bidding features.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-text">Bidding</h1>
        <div className="flex items-center gap-2">
          <Link href="/bidding/snipes">
            <Button variant="outline" size="sm">
              Snipes{stats ? ` (${stats.pending + stats.submitted + stats.active})` : ''}
            </Button>
          </Link>
          <Link href="/bidding/rules">
            <Button variant="outline" size="sm">Rules</Button>
          </Link>
          <Link href="/bidding/settings">
            <Button variant="outline" size="sm">Settings</Button>
          </Link>
        </div>
      </div>

      {/* Compact Stats Bar */}
      {stats && !statsLoading && (
        <div className="flex flex-wrap gap-4 mb-4 px-3 py-2 bg-panel-2/50 rounded-lg text-sm">
          <span className="text-text-2">Active: <span className="text-cyan-400 font-medium">{stats.pending + stats.submitted + stats.active}</span></span>
          <span className="text-text-2">Won: <span className="text-green-400 font-medium">{stats.won}</span></span>
          <span className="text-text-2">Lost: <span className="text-red-400 font-medium">{stats.lost}</span></span>
          {stats.win_rate !== null && (
            <span className="text-text-2">Win Rate: <span className="text-text font-medium">{stats.win_rate.toFixed(0)}%</span></span>
          )}
          {stats.total_spent > 0 && (
            <span className="text-text-2">Spent: <span className="text-text font-medium">${stats.total_spent.toFixed(0)}</span></span>
          )}
        </div>
      )}
      {statsError && (
        <p className="text-red-400 text-sm mb-4">{statsError}</p>
      )}

      {/* Recent Snipes (collapsible) */}
      {recentSnipes.length > 0 && (
        <div className="mb-4">
          <div className="flex gap-2 overflow-x-auto pb-2">
            {recentSnipes.map((sn) => (
              <div key={sn.id} className="flex-shrink-0 flex items-center gap-2 px-3 py-1.5 bg-panel border border-border rounded-lg text-xs">
                <span className="text-text truncate max-w-[150px]">{sn.item_title || sn.ebay_item_id}</span>
                <span className="text-text-2">${sn.max_bid.toFixed(0)}</span>
                <Badge className={`text-[10px] px-1.5 py-0 ${statusColor(sn.status)}`}>{sn.status}</Badge>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Search & Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <div className="flex-1 min-w-[200px]">
          <Input
            placeholder="Search eBay listings..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9"
          />
        </div>
        <select
          value={sport}
          onChange={(e) => { setSport(e.target.value); setPage(1); }}
          className="h-9 px-3 rounded-md border border-border bg-panel text-text text-sm"
        >
          <option value="">All Sports</option>
          <option value="BASKETBALL">Basketball</option>
          <option value="BASEBALL">Baseball</option>
          <option value="FOOTBALL">Football</option>
          <option value="HOCKEY">Hockey</option>
          <option value="SOCCER">Soccer</option>
        </select>
        <select
          value={sortBy}
          onChange={(e) => { setSortBy(e.target.value); setPage(1); }}
          className="h-9 px-3 rounded-md border border-border bg-panel text-text text-sm"
        >
          <option value="end_time">Ending Soon</option>
          <option value="price_low">Price: Low to High</option>
          <option value="price_high">Price: High to Low</option>
          <option value="bid_count">Most Bids</option>
          <option value="recent">Recently Added</option>
        </select>
      </div>

      {/* Results count */}
      <div className="flex items-center justify-between mb-3">
        <p className="text-sm text-text-2">
          {itemsLoading && items.length === 0
            ? 'Loading eBay auctions...'
            : `${total.toLocaleString()} eBay auctions`}
        </p>
      </div>

      {/* Item Grid */}
      {itemsLoading && items.length === 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {Array.from({ length: 20 }).map((_, i) => (
            <div key={i} className="bg-panel border border-border rounded-lg overflow-hidden">
              <div className="h-36 bg-panel-2 animate-pulse" />
              <div className="p-3 space-y-2">
                <div className="h-4 bg-panel-2 rounded animate-pulse" />
                <div className="h-3 bg-panel-2 rounded animate-pulse w-2/3" />
                <div className="h-8 bg-panel-2 rounded animate-pulse mt-2" />
              </div>
            </div>
          ))}
        </div>
      ) : items.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-text-2">No eBay auctions found. Listings are scraped every 30 minutes.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
            {items.map((item) => (
              <EbayItemCard
                key={item.id}
                item={item}
                onSnipe={() => openSnipeDialog(item)}
                isSniped={snipedItemIds.has(String(item.id))}
                formatCurrency={formatCurrency}
                formatTimeRemaining={formatTimeRemaining}
                isEndingSoon={isEndingSoon}
              />
            ))}
          </div>
          {hasMore && (
            <div className="flex justify-center mt-6">
              <Button
                variant="outline"
                onClick={loadMore}
                disabled={itemsLoading}
              >
                {itemsLoading ? 'Loading...' : 'Load More'}
              </Button>
            </div>
          )}
        </>
      )}

      {/* Snipe Dialog */}
      <Dialog open={!!snipeItem} onOpenChange={(open) => !open && setSnipeItem(null)}>
        <DialogContent className="sm:max-w-md bg-panel border-border">
          <DialogHeader>
            <DialogTitle className="text-text">Set Snipe</DialogTitle>
          </DialogHeader>
          {snipeItem && (
            <div className="space-y-4">
              {/* Item preview */}
              <div className="flex gap-3">
                {snipeItem.imageUrl && (
                  <div className="w-16 h-16 relative rounded overflow-hidden flex-shrink-0 bg-panel-2">
                    <Image
                      src={snipeItem.imageUrl}
                      alt=""
                      fill
                      className="object-contain"
                      unoptimized
                    />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-text line-clamp-2">{snipeItem.title}</p>
                  <p className="text-xs text-text-2 mt-1">
                    Current bid: {formatCurrency(snipeItem.currentBid)} &middot; {snipeItem.bidCount} bid{snipeItem.bidCount !== 1 ? 's' : ''} &middot; {formatTimeRemaining(snipeItem.endTime)}
                  </p>
                </div>
              </div>

              {/* Max bid input */}
              <div>
                <label className="text-sm text-text-2 block mb-1">Max Bid ($)</label>
                <Input
                  type="number"
                  step="0.01"
                  min="0.01"
                  value={maxBid}
                  onChange={(e) => setMaxBid(e.target.value)}
                  placeholder="Enter your max bid"
                  autoFocus
                />
                {snipeItem.currentBid && parseFloat(maxBid) > 0 && parseFloat(maxBid) <= snipeItem.currentBid && (
                  <p className="text-xs text-yellow-400 mt-1">
                    Bid is at or below current price ({formatCurrency(snipeItem.currentBid)})
                  </p>
                )}
              </div>

              {/* Bid offset */}
              <div>
                <label className="text-sm text-text-2 block mb-1">Snipe Timing (seconds before end)</label>
                <div className="flex gap-2">
                  {[3, 6, 8, 10, 15].map((sec) => (
                    <button
                      key={sec}
                      onClick={() => setBidOffset(sec)}
                      className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                        bidOffset === sec
                          ? 'bg-accent text-white'
                          : 'bg-panel-2 text-text-2 hover:text-text border border-border'
                      }`}
                    >
                      {sec}s
                    </button>
                  ))}
                </div>
              </div>

              {snipeError && <p className="text-sm text-red-400">{snipeError}</p>}
              {snipeSuccess && <p className="text-sm text-green-400">{snipeSuccess}</p>}

              <div className="flex gap-2 justify-end">
                <Button variant="outline" onClick={() => setSnipeItem(null)} disabled={snipeLoading}>
                  Cancel
                </Button>
                <Button onClick={handleSnipe} disabled={snipeLoading || !maxBid || !!snipeSuccess}>
                  {snipeLoading ? 'Setting...' : 'Set Snipe'}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

// --- Sub-components ---

function EbayItemCard({
  item,
  onSnipe,
  isSniped,
  formatCurrency,
  formatTimeRemaining,
  isEndingSoon,
}: {
  item: AuctionItem;
  onSnipe: () => void;
  isSniped: boolean;
  formatCurrency: (n?: number) => string;
  formatTimeRemaining: (s?: string) => string;
  isEndingSoon: (s?: string) => boolean;
}) {
  const [imgError, setImgError] = useState(false);

  return (
    <div className="bg-panel border border-border rounded-lg overflow-hidden flex flex-col hover:border-accent/50 transition-colors">
      {/* Image */}
      <div className="relative bg-panel-2">
        {isEndingSoon(item.endTime) && (
          <div className="absolute top-1.5 left-1.5 z-10">
            <div className="bg-red-500/90 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded flex items-center gap-0.5 animate-pulse">
              <Clock className="w-2.5 h-2.5" />
              Soon
            </div>
          </div>
        )}
        {item.gradingCompany && item.grade && (
          <div className="absolute top-1.5 right-1.5 z-10">
            <span className="bg-accent/90 text-white text-[10px] font-semibold px-1.5 py-0.5 rounded">
              {item.gradingCompany} {item.grade}
            </span>
          </div>
        )}
        {item.imageUrl && !imgError ? (
          <div className="w-full h-32 sm:h-40 relative">
            <Image
              src={item.imageUrl}
              alt={item.title}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              className="object-contain p-2"
              loading="lazy"
              unoptimized
              onError={() => setImgError(true)}
            />
          </div>
        ) : (
          <div className="w-full h-32 sm:h-40 flex items-center justify-center">
            <svg className="w-8 h-8 text-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-2 sm:p-3 flex flex-col flex-1">
        <h3 className="text-xs sm:text-sm font-medium text-text line-clamp-2 mb-1.5 min-h-[2rem] leading-snug">
          {item.title}
        </h3>
        <div className="mb-2">
          <span className="text-base sm:text-lg font-bold text-text">{formatCurrency(item.currentBid)}</span>
          <div className="flex items-center gap-1.5 text-[10px] sm:text-xs text-text-2 mt-0.5">
            {item.bidCount > 0 && <span>{item.bidCount} bid{item.bidCount !== 1 ? 's' : ''}</span>}
            <span className={isEndingSoon(item.endTime) ? 'text-red-400 font-medium' : ''}>
              {formatTimeRemaining(item.endTime)}
            </span>
          </div>
        </div>

        <div className="mt-auto flex gap-1.5">
          {isSniped ? (
            <div className="flex-1 py-1.5 text-center text-xs font-medium text-green-400 bg-green-500/10 border border-green-500/30 rounded-md">
              Snipe Set
            </div>
          ) : (
            <button
              onClick={onSnipe}
              className="flex-1 py-1.5 text-xs sm:text-sm font-medium text-white bg-accent hover:bg-accent/80 rounded-md transition-colors active:scale-[0.98]"
            >
              Snipe
            </button>
          )}
          {item.itemUrl && (
            <a
              href={item.itemUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="px-2 py-1.5 text-text-2 hover:text-text border border-border rounded-md transition-colors flex items-center"
              title="View on eBay"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

