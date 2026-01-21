'use client';

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useQuery, useLazyQuery } from '@apollo/client/react';
import { gql } from '@apollo/client';
import { AuctionCard } from './AuctionCard';
import { AuctionGridSkeleton } from './AuctionCardSkeleton';
import { FilterBar } from './FilterBar';
import { AuctionItem } from '@/lib/types';
import { useAuth } from '@/lib/providers/AuthProvider';
import { useFilters, type SortOption, type ItemTypeFilter, type SportFilterType } from '@/lib/providers/FilterProvider';
import { savedSearchesAPI, SavedSearch, SavedSearchFilters } from '@/lib/api/savedSearches';
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

// Fragment for auction item fields
const AUCTION_ITEM_FIELDS = `
  id
  title
  description
  currentBid
  startingBid
  bidCount
  endTime
  imageUrl
  itemUrl
  auctionHouse
  lotNumber
  gradingCompany
  grade
  certNumber
  category
  sport
  status
  isWatched
  marketValueLow
  marketValueHigh
  marketValueAvg
  marketValueConfidence
`;

// Initial fast load - just first batch for immediate display
const GET_INITIAL_ITEMS = gql`
  query GetInitialItems {
    auctionItems(page: 1, pageSize: 500, status: "Live") {
      items {
        ${AUCTION_ITEM_FIELDS}
      }
      total
    }
  }
`;

// Batch query for background loading
const GET_ITEMS_BATCH = gql`
  query GetItemsBatch($page: Int!, $pageSize: Int!) {
    auctionItems(page: $page, pageSize: $pageSize, status: "Live") {
      items {
        ${AUCTION_ITEM_FIELDS}
      }
      total
    }
  }
`;

// Helper to detect if an item is a trading card
const isCardItem = (item: AuctionItem): boolean => {
  // Has grading = definitely a card
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
  // Autograph but NOT a card (cards with autos are still cards)
  return autographKeywords.some(kw => title.includes(kw)) && !isCardItem(item);
};

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
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Saved searches state
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>([]);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [loadingSavedSearches, setLoadingSavedSearches] = useState(false);

  // Progressive loading state
  const [allItems, setAllItems] = useState<AuctionItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [loadingProgress, setLoadingProgress] = useState(0);
  const backgroundLoadingRef = useRef(false);

  // Initial fast load - first 500 items
  const { data: initialData, loading: initialLoading, error } = useQuery<{ auctionItems: { items: AuctionItem[]; total: number } }>(
    GET_INITIAL_ITEMS,
    {
      fetchPolicy: 'cache-first',
      nextFetchPolicy: 'cache-and-network',
    }
  );

  // Lazy query for background batch loading
  const [fetchBatch] = useLazyQuery<{ auctionItems: { items: AuctionItem[]; total: number } }>(
    GET_ITEMS_BATCH,
    { fetchPolicy: 'network-only' }
  );

  // Load initial items when they arrive
  useEffect(() => {
    if (initialData?.auctionItems) {
      setAllItems(initialData.auctionItems.items);
      setTotalItems(initialData.auctionItems.total);
    }
  }, [initialData]);

  // Background loading of remaining items
  const loadRemainingItems = useCallback(async () => {
    if (backgroundLoadingRef.current) return;
    if (!initialData?.auctionItems) return;

    const total = initialData.auctionItems.total;
    const initialCount = initialData.auctionItems.items.length;

    // If we already have all items, skip
    if (initialCount >= total) return;

    backgroundLoadingRef.current = true;
    setIsLoadingMore(true);

    const BATCH_SIZE = 2000;
    const itemsMap = new Map<number, AuctionItem>();

    // Add initial items to map
    initialData.auctionItems.items.forEach(item => {
      itemsMap.set(item.id, item);
    });

    // Calculate how many batches we need (starting from page 2 since we have page 1)
    const startPage = Math.ceil(initialCount / BATCH_SIZE) + 1;
    const totalPages = Math.ceil(total / BATCH_SIZE);

    for (let batchPage = startPage; batchPage <= totalPages; batchPage++) {
      try {
        const { data } = await fetchBatch({
          variables: { page: batchPage, pageSize: BATCH_SIZE }
        });

        if (data?.auctionItems?.items) {
          // Add new items to map (deduplicates by ID)
          data.auctionItems.items.forEach(item => {
            itemsMap.set(item.id, item);
          });

          // Update state with merged items
          const mergedItems = Array.from(itemsMap.values());
          setAllItems(mergedItems);
          setLoadingProgress(Math.min(100, Math.round((mergedItems.length / total) * 100)));
        }
      } catch (err) {
        console.error('Error loading batch:', err);
        break;
      }
    }

    setIsLoadingMore(false);
    setLoadingProgress(100);
    backgroundLoadingRef.current = false;
  }, [initialData, fetchBatch]);

  // Start background loading after initial data arrives
  useEffect(() => {
    if (initialData?.auctionItems && !backgroundLoadingRef.current) {
      // Small delay to let the UI render first
      const timer = setTimeout(() => {
        loadRemainingItems();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [initialData, loadRemainingItems]);

  const loading = initialLoading && allItems.length === 0;

  // Client-side filtering and sorting
  const filteredAndSortedItems = useMemo(() => {
    let result = [...allItems];

    // Filter out ended auctions (endTime has passed)
    const now = new Date();
    result = result.filter(item => {
      if (!item.endTime) return true; // Keep items without endTime
      const endTime = new Date(item.endTime.includes('Z') || item.endTime.includes('+') ? item.endTime : item.endTime + 'Z');
      return endTime > now;
    });

    // Filter by auction house
    if (auctionHouse) {
      result = result.filter(item => item.auctionHouse === auctionHouse);
    }

    // Filter by search term (wildcard search - all words must match in any order)
    if (searchInput.trim()) {
      const searchWords = searchInput.toLowerCase().trim().split(/\s+/).filter(Boolean);
      result = result.filter(item => {
        const searchableText = [
          item.title,
          item.description,
          item.category,
          item.gradingCompany,
          item.grade,
          item.lotNumber,
        ].filter(Boolean).join(' ').toLowerCase();
        // All search words must be found somewhere in the searchable text
        return searchWords.every(word => searchableText.includes(word));
      });
    }

    // Filter by min price
    if (minPrice) {
      const min = parseFloat(minPrice);
      if (!isNaN(min)) {
        result = result.filter(item => (item.currentBid || 0) >= min);
      }
    }

    // Filter by max price
    if (maxPrice) {
      const max = parseFloat(maxPrice);
      if (!isNaN(max)) {
        result = result.filter(item => (item.currentBid || 0) <= max);
      }
    }

    // Filter by item type
    if (itemType === 'cards') {
      result = result.filter(isCardItem);
    } else if (itemType === 'memorabilia') {
      result = result.filter(isMemorabiliaItem);
    } else if (itemType === 'autographs') {
      result = result.filter(isAutographItem);
    }

    // Filter by sport
    if (sport) {
      result = result.filter(item => item.sport === sport);
    }

    // Sort
    switch (sortBy) {
      case 'endTime':
        result.sort((a, b) => {
          if (!a.endTime) return 1;
          if (!b.endTime) return -1;
          return new Date(a.endTime).getTime() - new Date(b.endTime).getTime();
        });
        break;
      case 'priceLow':
        result.sort((a, b) => (a.currentBid || 0) - (b.currentBid || 0));
        break;
      case 'priceHigh':
        result.sort((a, b) => (b.currentBid || 0) - (a.currentBid || 0));
        break;
      case 'bidCount':
        result.sort((a, b) => (b.bidCount || 0) - (a.bidCount || 0));
        break;
      case 'recent':
        result.sort((a, b) => b.id - a.id);
        break;
      case 'bestValue':
        // Sort by lowest % of estimated value (best deals first)
        // Items with market value data come first, sorted by value percentage
        // Items without market value data are sorted to the end by price
        result.sort((a, b) => {
          const aHasValue = a.currentBid && a.currentBid > 0 && a.marketValueAvg && a.marketValueAvg > 0;
          const bHasValue = b.currentBid && b.currentBid > 0 && b.marketValueAvg && b.marketValueAvg > 0;

          // Items with value data come before those without
          if (aHasValue && !bHasValue) return -1;
          if (!aHasValue && bHasValue) return 1;

          // Both have value data - sort by value percentage
          if (aHasValue && bHasValue) {
            const aPercent = (a.currentBid || 0) / (a.marketValueAvg || 1);
            const bPercent = (b.currentBid || 0) / (b.marketValueAvg || 1);
            return aPercent - bPercent;
          }

          // Neither has value data - sort by price low to high
          return (a.currentBid || 0) - (b.currentBid || 0);
        });
        break;
    }

    return result;
  }, [allItems, auctionHouse, searchInput, sortBy, minPrice, maxPrice, itemType, sport]);

  // Client-side pagination
  const totalFiltered = filteredAndSortedItems.length;
  const totalPages = Math.ceil(totalFiltered / pageSize);
  const startIndex = (page - 1) * pageSize;
  const paginatedItems = filteredAndSortedItems.slice(startIndex, startIndex + pageSize);
  const hasMore = page < totalPages;

  // Reset to page 1 when filters change
  useEffect(() => {
    setPage(1);
  }, [searchInput, auctionHouse, sortBy, minPrice, maxPrice, itemType, sport]);

  // Ensure page stays within valid range when filtered results change
  useEffect(() => {
    if (totalPages > 0 && page > totalPages) {
      setPage(totalPages);
    }
  }, [totalPages, page]);

  // Scroll to top when page changes
  useEffect(() => {
    window.scrollTo(0, 0);
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [page]);

  // Fetch saved searches when user changes
  useEffect(() => {
    if (user) {
      // Check if token is actually available before fetching
      const token = localStorage.getItem('access_token');
      if (token) {
        fetchSavedSearches();
      }
    } else {
      setSavedSearches([]);
    }
  }, [user]);

  const fetchSavedSearches = async () => {
    // Double-check token exists to avoid 401 errors
    const token = localStorage.getItem('access_token');
    if (!token) return;

    try {
      setLoadingSavedSearches(true);
      const searches = await savedSearchesAPI.list();
      setSavedSearches(searches);
    } catch (err) {
      // Silently ignore auth errors - user may have logged out
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
    setPage(1);
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

  // Show skeleton during SSR and initial load for consistent hydration
  if (!mounted || (loading && allItems.length === 0)) {
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

  if (error && allItems.length === 0) {
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
          totalFiltered={totalFiltered}
          totalItems={totalItems}
          isLoadingMore={isLoadingMore}
          loadingProgress={loadingProgress}
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
        {paginatedItems.length === 0 ? (
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
              {paginatedItems.map((item) => (
                <AuctionCard key={item.id} item={item} />
              ))}
            </div>

            {/* Pagination - Mobile Optimized */}
            <div className="flex items-center justify-center gap-2 sm:gap-4 mt-8 pb-safe">
              <Button
                variant="outline"
                onClick={() => setPage(page - 1)}
                disabled={page === 1}
                className="px-3 sm:px-6"
              >
                <ChevronLeftIcon className="w-4 h-4 sm:mr-1" />
                <span className="hidden sm:inline">Previous</span>
              </Button>
              <div className="flex items-center gap-1 sm:gap-2 text-text-2 text-sm sm:text-base">
                <input
                  type="number"
                  min={1}
                  max={totalPages}
                  value={page}
                  onChange={(e) => {
                    const newPage = parseInt(e.target.value, 10);
                    if (!isNaN(newPage) && newPage >= 1) {
                      // Clamp to valid range immediately
                      setPage(Math.min(newPage, totalPages || 1));
                    }
                  }}
                  onBlur={(e) => {
                    const newPage = parseInt(e.target.value, 10);
                    if (isNaN(newPage) || newPage < 1) {
                      setPage(1);
                    } else if (newPage > totalPages) {
                      setPage(totalPages);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.currentTarget.blur();
                    }
                  }}
                  className="w-12 sm:w-16 text-center bg-panel border border-border rounded px-1 py-1 text-text [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <span>/ {totalPages}</span>
              </div>
              <Button
                variant="outline"
                onClick={() => setPage(page + 1)}
                disabled={!hasMore}
                className="px-3 sm:px-6"
              >
                <span className="hidden sm:inline">Next</span>
                <ChevronRightIcon className="w-4 h-4 sm:ml-1" />
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
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

function ChevronLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  );
}

function ChevronRightIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  );
}
