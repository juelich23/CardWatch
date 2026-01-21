'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { aiSearchAPI, AISearchResponse, SearchSuggestion } from '@/lib/api/aiSearch';
import { useFilters, type SortOption, type ItemTypeFilter, type SportFilterType } from '@/lib/providers/FilterProvider';

interface AISearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// Map AI sport values to our filter values (must be uppercase)
const normalizeSport = (sport: string | null | undefined): SportFilterType => {
  if (!sport) return '';
  const upper = sport.toUpperCase();
  const validSports: SportFilterType[] = ['BASKETBALL', 'BASEBALL', 'FOOTBALL', 'HOCKEY', 'SOCCER', 'GOLF', 'BOXING', 'RACING', 'OTHER'];
  // Map common variations
  if (upper === 'MMA' || upper === 'UFC') return 'OTHER';
  if (validSports.includes(upper as SportFilterType)) {
    return upper as SportFilterType;
  }
  return '';
};

export function AISearchModal({ isOpen, onClose }: AISearchModalProps) {
  const router = useRouter();
  const {
    setSearchInput,
    setAuctionHouse,
    setItemType,
    setSport,
    setSortBy,
    setMinPrice,
    setMaxPrice,
  } = useFilters();

  const [query, setQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AISearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<SearchSuggestion[]>([]);

  // Load suggestions on mount
  useEffect(() => {
    if (isOpen && suggestions.length === 0) {
      aiSearchAPI.getSuggestions()
        .then(data => setSuggestions(data.suggestions))
        .catch(() => {});
    }
  }, [isOpen, suggestions.length]);

  // Reset state when modal closes
  useEffect(() => {
    if (!isOpen) {
      setQuery('');
      setResult(null);
      setError(null);
      setIsLoading(false);
    }
  }, [isOpen]);

  // Handle escape key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  const applySearch = useCallback((searchResult: AISearchResponse) => {
    // Apply the interpreted search
    setSearchInput(searchResult.search_terms || '');

    // Apply filters
    const filters = searchResult.filters;
    if (filters.auction_house) {
      setAuctionHouse(filters.auction_house);
    }
    if (filters.item_type) {
      setItemType(filters.item_type as ItemTypeFilter);
    }
    if (filters.sport) {
      const normalizedSport = normalizeSport(filters.sport);
      if (normalizedSport) {
        setSport(normalizedSport);
      }
    }
    if (filters.sort_by) {
      setSortBy(filters.sort_by as SortOption);
    }
    if (filters.min_price) {
      setMinPrice(filters.min_price.toString());
    }
    if (filters.max_price) {
      setMaxPrice(filters.max_price.toString());
    }

    // Navigate to home and close modal
    router.push('/');
    onClose();
  }, [router, onClose, setSearchInput, setAuctionHouse, setItemType, setSport, setSortBy, setMinPrice, setMaxPrice]);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await aiSearchAPI.search(query);
      // Auto-apply the search results immediately
      applySearch(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
      setIsLoading(false);
    }
  }, [query, applySearch]);

  const handleSuggestionClick = (suggestion: string) => {
    setQuery(suggestion);
    // Auto-search and apply when clicking suggestion
    setTimeout(() => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      aiSearchAPI.search(suggestion)
        .then(response => {
          // Auto-apply the search results immediately
          applySearch(response);
        })
        .catch(err => {
          setError(err instanceof Error ? err.message : 'Search failed');
          setIsLoading(false);
        });
    }, 100);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-start justify-center pt-[10vh]"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: -20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -20 }}
          transition={{ duration: 0.2 }}
          className="bg-panel border border-border rounded-xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden"
          onClick={e => e.stopPropagation()}
        >
          {/* Header */}
          <div className="px-6 py-4 border-b border-border flex items-center gap-3">
            <SparklesIcon className="w-5 h-5 text-accent" />
            <span className="text-lg font-semibold text-text">AI Search</span>
            <span className="text-sm text-muted ml-2">Describe what you're looking for</span>
          </div>

          {/* Search Input */}
          <div className="p-4 border-b border-border">
            <div className="flex gap-2">
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSearch()}
                placeholder="e.g., rookie Justin Jefferson cards, PSA 10 Jordan under $500..."
                className="flex-1 px-4 py-3 bg-panel-2 border border-border text-text placeholder:text-muted rounded-lg focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent text-base"
                autoFocus
              />
              <button
                onClick={handleSearch}
                disabled={isLoading || !query.trim()}
                className="px-6 py-3 bg-accent hover:bg-accent/80 disabled:bg-accent/50 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
              >
                {isLoading ? (
                  <LoadingSpinner />
                ) : (
                  <SearchIcon className="w-4 h-4" />
                )}
                Search
              </button>
            </div>
          </div>

          {/* Content Area */}
          <div className="max-h-[50vh] overflow-y-auto">
            {/* Error */}
            {error && (
              <div className="p-4 m-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                <p className="text-red-400 text-sm">{error}</p>
              </div>
            )}

            {/* Result */}
            {result && !error && (
              <div className="p-4 space-y-4">
                {/* Explanation */}
                <div className="bg-accent/10 border border-accent/30 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <SparklesIcon className="w-5 h-5 text-accent mt-0.5" />
                    <div>
                      <p className="text-text font-medium">{result.explanation}</p>
                      {result.search_terms && (
                        <p className="text-muted text-sm mt-1">
                          Searching for: <span className="text-text">{result.search_terms}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Detected Filters */}
                {(result.filters.auction_house || result.filters.item_type ||
                  result.filters.min_price || result.filters.max_price ||
                  result.filters.sort_by || result.player_name || result.year) && (
                  <div className="space-y-2">
                    <p className="text-sm text-muted font-medium">Detected filters:</p>
                    <div className="flex flex-wrap gap-2">
                      {result.player_name && (
                        <FilterTag label="Player" value={result.player_name} />
                      )}
                      {result.year && (
                        <FilterTag label="Year" value={result.year} />
                      )}
                      {result.is_rookie && (
                        <FilterTag label="Type" value="Rookie" />
                      )}
                      {result.filters.auction_house && (
                        <FilterTag label="Auction House" value={result.filters.auction_house} />
                      )}
                      {result.filters.item_type && (
                        <FilterTag label="Category" value={result.filters.item_type} />
                      )}
                      {result.filters.min_price && (
                        <FilterTag label="Min Price" value={`$${result.filters.min_price}`} />
                      )}
                      {result.filters.max_price && (
                        <FilterTag label="Max Price" value={`$${result.filters.max_price}`} />
                      )}
                      {result.filters.grading_company && (
                        <FilterTag label="Grading" value={result.filters.grading_company} />
                      )}
                      {result.filters.sort_by && (
                        <FilterTag label="Sort" value={result.filters.sort_by} />
                      )}
                    </div>
                  </div>
                )}

                {/* Apply Button - kept as fallback if auto-apply fails */}
                <button
                  onClick={() => result && applySearch(result)}
                  className="w-full py-3 bg-accent hover:bg-accent/80 text-white font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  <SearchIcon className="w-4 h-4" />
                  Find Matching Items
                </button>
              </div>
            )}

            {/* Suggestions (when no result) */}
            {!result && !error && !isLoading && (
              <div className="p-4">
                <p className="text-sm text-muted font-medium mb-3">Try searching for:</p>
                <div className="grid gap-2">
                  {suggestions.map((suggestion, i) => (
                    <button
                      key={i}
                      onClick={() => handleSuggestionClick(suggestion.query)}
                      className="text-left px-4 py-3 bg-panel-2 hover:bg-hover rounded-lg transition-colors group"
                    >
                      <p className="text-text group-hover:text-accent transition-colors">
                        "{suggestion.query}"
                      </p>
                      <p className="text-sm text-muted mt-0.5">{suggestion.description}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Loading */}
            {isLoading && (
              <div className="p-8 flex flex-col items-center justify-center">
                <LoadingSpinner className="w-8 h-8 text-accent" />
                <p className="text-muted mt-3">Analyzing your search...</p>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-4 py-3 border-t border-border bg-panel-2 flex items-center justify-between">
            <p className="text-xs text-muted">Press Escape to close</p>
            <button
              onClick={onClose}
              className="text-sm text-muted hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function FilterTag({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-panel-2 border border-border rounded-md text-sm">
      <span className="text-muted">{label}:</span>
      <span className="text-text font-medium">{value}</span>
    </span>
  );
}

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function LoadingSpinner({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
    </svg>
  );
}
