'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useQuery } from '@apollo/client/react';
import { AuctionCard } from './AuctionCard';
import { AuctionGridSkeleton } from './AuctionCardSkeleton';
import { FilterBar } from './FilterBar';
import { AuctionItem } from '@/lib/types';
import { useAuth } from '@/lib/providers/AuthProvider';
import { useFilters, type SortOption, type ItemTypeFilter, type SportFilterType } from '@/lib/providers/FilterProvider';
import { savedSearchesAPI, SavedSearch, SavedSearchFilters } from '@/lib/api/savedSearches';
import { GET_AUCTION_ITEMS } from '@/lib/graphql/queries';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import dynamic from 'next/dynamic';

// Dynamically import SaveSearchModal - only loaded when save button is clicked
const SaveSearchModal = dynamic(
  () => import('./SaveSearchModal').then(mod => ({ default: mod.SaveSearchModal })),
  { ssr: false, loading: () => null }
);

// Map frontend sort options to backend sort_by values
const sortByMap: Record<SortOption, string> = {
  endTime: 'end_time',
  priceLow: 'price_low',
  priceHigh: 'price_high',
  bidCount: 'bid_count',
  recent: 'recent',
  bestValue: 'end_time', // bestValue requires client-side sorting (needs market value data)
};

// Map frontend itemType to category filter for server
const itemTypeToCategory: Record<ItemTypeFilter, string | undefined> = {
  '': undefined,
  cards: undefined, // Cards filter needs client-side (based on title keywords)
  memorabilia: undefined, // Same
  autographs: undefined, // Same
};

// Helper to detect if an item is a trading card
const isCardItem = (item: AuctionItem): boolean => {
  if (item.gradingCompany) return true;
  const title = (item.title || '').toLowerCase();
  const cardKeywords = [
    'card', 'rookie', 'topps', 'panini', 'bowman', 'fleer', 'upper deck',
    'prizm', 'chrome', 'refractor', 'auto #', '/10', '/25', '/50', '/99',
    'psa', 'bgs', 'sgc', 'cgc', 'gem mint', 'mint 9', 'mint 10'
  ];
  return cardKeywords.some(kw => title.includes(kw));
};

const isMemorabiliaItem = (item: AuctionItem): boolean => {
  const title = (item.title || '').toLowerCase();
  const memorabiliaKeywords = [
    'jersey', 'helmet', 'ball', 'bat', 'glove', 'cleats', 'shoes',
    'game-used', 'game used', 'game worn', 'equipment', 'ring', 'trophy',
    'ticket', 'stub', 'program', 'photo', 'poster', 'pennant'
  ];
  return memorabiliaKeywords.some(kw => title.includes(kw)) && !isCardItem(item);
};

const isAutographItem = (item: AuctionItem): boolean => {
  const title = (item.title || '').toLowerCase();
  const autographKeywords = ['signed', 'autograph', 'signature', 'auto '];
  return autographKeywords.some(kw => title.includes(kw)) && !isCardItem(item);
};

// Apply client-side item type filter
const filterByItemType = (items: AuctionItem[], itemType: ItemTypeFilter): AuctionItem[] => {
  if (!itemType) return items;
  if (itemType === 'cards') return items.filter(isCardItem);
  if (itemType === 'memorabilia') return items.filter(isMemorabiliaItem);
  if (itemType === 'autographs') return items.filter(isAutographItem);
  return items;
};

// Apply client-side bestValue sorting
const sortByBestValue = (items: AuctionItem[]): AuctionItem[] => {
  return [...items].sort((a, b) => {
    const aHasValue = a.currentBid && a.currentBid > 0 && a.marketValueAvg && a.marketValueAvg > 0;
    const bHasValue = b.currentBid && b.currentBid > 0 && b.marketValueAvg && b.marketValueAvg > 0;

    if (aHasValue && !bHasValue) return -1;
    if (!aHasValue && bHasValue) return 1;

    if (aHasValue && bHasValue) {
      const aPercent = (a.currentBid || 0) / (a.marketValueAvg || 1);
      const bPercent = (b.currentBid || 0) / (b.marketValueAvg || 1);
      return aPercent - bPercent;
    }

    return (a.currentBid || 0) - (b.currentBid || 0);
  });
};

const PAGE_SIZE = 40;

export function AuctionList() {
  const { user } = useAuth();
  const {
    searchInput,
    auctionHouse,
    sortBy,
    minPrice,
    maxPrice,
    itemType,
    sport,
    setSearchInput,
    setAuctionHouse,
    setSortBy,
    setMinPrice,
    setMaxPrice,
    setItemType,
    setSport,
    clearFilters,
  } = useFilters();

  const [mounted, setMounted] = useState(false);
  const [displayedItems, setDisplayedItems] = useState<AuctionItem[]>([]);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Use refs to avoid stale closures in the observer callback
  const currentPageRef = useRef(1);
  const hasMoreRef = useRef(true);
  const isLoadingMoreRef = useRef(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Saved searches state
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [loadingSavedSearches, setLoadingSavedSearches] = useState(false);

  // Memoize query variables to prevent unnecessary re-renders
  const queryVariables = useMemo(() => ({
    page: 1,
    pageSize: PAGE_SIZE,
    status: 'Live',
    auctionHouse: auctionHouse || undefined,
    sport: sport || undefined,
    search: searchInput.trim() || undefined,
    minBid: minPrice ? parseFloat(minPrice) : undefined,
    maxBid: maxPrice ? parseFloat(maxPrice) : undefined,
    sortBy: sortByMap[sortBy] || 'end_time',
  }), [auctionHouse, sport, searchInput, minPrice, maxPrice, sortBy]);

  // Main query with server-side filtering
  const { data, loading, error, fetchMore } = useQuery<{
    auctionItems: { items: AuctionItem[]; total: number; hasMore: boolean };
  }>(GET_AUCTION_ITEMS, {
    variables: queryVariables,
    fetchPolicy: 'cache-and-network',
  });

  // Reset when filters change
  useEffect(() => {
    currentPageRef.current = 1;
    hasMoreRef.current = true;
    setDisplayedItems([]);
  }, [searchInput, auctionHouse, sortBy, minPrice, maxPrice, itemType, sport]);

  // Process initial data (page 1)
  useEffect(() => {
    if (data?.auctionItems?.items && currentPageRef.current === 1) {
      let items = [...data.auctionItems.items];
      items = filterByItemType(items, itemType);
      if (sortBy === 'bestValue') {
        items = sortByBestValue(items);
      }
      setDisplayedItems(items);
      hasMoreRef.current = data.auctionItems.hasMore;
    }
  }, [data, itemType, sortBy]);

  // Load more items function using refs to avoid stale closures
  const loadMoreItems = useCallback(async () => {
    if (isLoadingMoreRef.current || !hasMoreRef.current) return;

    isLoadingMoreRef.current = true;
    setIsLoadingMore(true);

    const nextPage = currentPageRef.current + 1;

    try {
      const result = await fetchMore({
        variables: { ...queryVariables, page: nextPage },
      });

      if (result.data?.auctionItems?.items) {
        let newItems = [...result.data.auctionItems.items];
        newItems = filterByItemType(newItems, itemType);

        setDisplayedItems(prev => {
          const existingIds = new Set(prev.map(item => item.id));
          const uniqueNewItems = newItems.filter(item => !existingIds.has(item.id));

          if (sortBy === 'bestValue') {
            return sortByBestValue([...prev, ...uniqueNewItems]);
          }
          return [...prev, ...uniqueNewItems];
        });

        currentPageRef.current = nextPage;
        hasMoreRef.current = result.data.auctionItems.hasMore;
      }
    } catch (err) {
      console.error('Error loading more items:', err);
    } finally {
      isLoadingMoreRef.current = false;
      setIsLoadingMore(false);
    }
  }, [fetchMore, queryVariables, itemType, sortBy]);

  // Infinite scroll observer - set up once and use refs for current values
  useEffect(() => {
    const sentinel = loadMoreRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !isLoadingMoreRef.current && hasMoreRef.current) {
          loadMoreItems();
        }
      },
      { rootMargin: '600px', threshold: 0 }
    );

    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [loadMoreItems]);

  const totalItems = data?.auctionItems?.total || 0;
  const hasMore = hasMoreRef.current;

  // Fetch saved searches when user changes
  useEffect(() => {
    if (user) {
      const token = localStorage.getItem('access_token');
      if (token) {
        fetchSavedSearches();
      }
    } else {
      setSavedSearches([]);
    }
  }, [user]);

  const fetchSavedSearches = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      setLoadingSavedSearches(true);
      const searches = await savedSearchesAPI.list();
      setSavedSearches(searches);
    } catch (err) {
      if (!(err instanceof Error && err.message.includes('sign in'))) {
        console.error('Error fetching saved searches:', err);
      }
    } finally {
      setLoadingSavedSearches(false);
    }
  };

  const getCurrentFilters = (): SavedSearchFilters => {
    return {
      search: searchInput || undefined,
      auctionHouse: auctionHouse || undefined,
      itemType: itemType || undefined,
      sport: sport || undefined,
      minPrice: minPrice ? parseFloat(minPrice) : undefined,
      maxPrice: maxPrice ? parseFloat(maxPrice) : undefined,
      sortBy: sortBy || undefined,
    };
  };

  const handleSaveSearch = async (name: string) => {
    await savedSearchesAPI.create(name, getCurrentFilters());
    await fetchSavedSearches();
  };

  const handleLoadSearch = (search: SavedSearch) => {
    const filters = search.filters;
    setSearchInput(filters.search || '');
    setAuctionHouse(filters.auctionHouse || '');
    setItemType((filters.itemType as ItemTypeFilter) || '');
    setSport((filters.sport as SportFilterType) || '');
    setMinPrice(filters.minPrice?.toString() || '');
    setMaxPrice(filters.maxPrice?.toString() || '');
    setSortBy((filters.sortBy as SortOption) || 'endTime');
  };

  const handleDeleteSearch = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await savedSearchesAPI.delete(id);
      setSavedSearches(savedSearches.filter(s => s.id !== id));
    } catch (err) {
      console.error('Error deleting saved search:', err);
    }
  };

  const hasActiveFilters = searchInput || auctionHouse || minPrice || maxPrice || itemType || sport;

  // Show skeleton during SSR and initial load
  if (!mounted || (loading && displayedItems.length === 0)) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <h1 className="text-4xl font-bold text-text">Auction Items</h1>
          <p className="text-text-2 mt-2">Loading items...</p>
        </div>
        <AuctionGridSkeleton count={20} />
      </div>
    );
  }

  if (error && displayedItems.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center text-danger">
          <p className="text-xl font-semibold">Error loading auction items</p>
          <p className="mt-2 text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-6 sm:py-8">
      {/* Header - Mobile Optimized */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-4xl font-bold text-text">Auctions</h1>
            <span className="text-xs text-muted bg-panel px-2 py-1 rounded">v0.2</span>
          </div>

          {/* Saved Searches Actions - Compact on Mobile */}
          <div className="flex items-center gap-2">
            {user && hasActiveFilters && (
              <Button
                size="sm"
                onClick={() => setShowSaveModal(true)}
                className="h-9"
              >
                <BookmarkIcon className="w-4 h-4 sm:mr-1" />
                <span className="hidden sm:inline">Save</span>
              </Button>
            )}

            {user && savedSearches.length > 0 && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="sm" className="h-9">
                    <FolderIcon className="w-4 h-4 sm:mr-1" />
                    <span className="hidden sm:inline">Saved</span>
                    <span className="ml-1 bg-accent/20 text-accent text-xs px-1.5 rounded-full">
                      {savedSearches.length}
                    </span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 bg-panel border-border">
                  {savedSearches.map((search) => (
                    <DropdownMenuItem
                      key={search.id}
                      onClick={() => handleLoadSearch(search)}
                      className="flex items-center justify-between cursor-pointer text-text hover:bg-hover"
                    >
                      <span className="truncate">{search.name}</span>
                      <button
                        onClick={(e) => handleDeleteSearch(search.id, e)}
                        className="text-muted hover:text-red-400 ml-2 p-1"
                      >
                        <XIcon className="w-3 h-3" />
                      </button>
                    </DropdownMenuItem>
                  ))}
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </div>
        </div>
      </div>

      {/* Filters - Using New FilterBar Component */}
      <div className="mb-6">
        <FilterBar
          totalFiltered={displayedItems.length}
          totalItems={totalItems}
          isLoadingMore={isLoadingMore}
          loadingProgress={100}
        />
      </div>

      {/* Save Search Modal */}
      <SaveSearchModal
        isOpen={showSaveModal}
        onClose={() => setShowSaveModal(false)}
        onSave={handleSaveSearch}
      />

      {/* Grid */}
      <AnimatePresence mode="wait">
        {displayedItems.length === 0 && !loading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="text-center py-12"
          >
            <p className="text-muted text-lg">No auction items found</p>
            {hasActiveFilters && (
              <Button variant="outline" className="mt-4" onClick={clearFilters}>
                Clear Filters
              </Button>
            )}
          </motion.div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            {/* Responsive Grid - 2 cols on mobile for better use of space */}
            <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-3 sm:gap-4 md:gap-6 mb-8">
              {displayedItems.map((item) => (
                <AuctionCard key={item.id} item={item} />
              ))}
            </div>

            {/* Infinite Scroll Sentinel */}
            <div ref={loadMoreRef} className="flex justify-center py-8">
              {isLoadingMore && (
                <div className="flex items-center gap-2 text-text-2">
                  <LoadingSpinner />
                  <span>Loading more items...</span>
                </div>
              )}
              {!hasMore && displayedItems.length > 0 && (
                <p className="text-muted text-sm">
                  Showing all {displayedItems.length.toLocaleString()} items
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Loading spinner component
function LoadingSpinner() {
  return (
    <svg className="animate-spin h-5 w-5 text-accent" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
    </svg>
  );
}

// Icons
function BookmarkIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
    </svg>
  );
}

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}
