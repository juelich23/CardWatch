'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useFilters, type SortOption, type ItemTypeFilter, type SportFilterType } from '@/lib/providers/FilterProvider';
import { useAISearch } from '@/lib/providers/AISearchProvider';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';
import { Badge } from '@/components/ui/badge';

const auctionHouses = [
  { value: 'goldin', label: 'Goldin' },
  { value: 'fanatics', label: 'Fanatics Collect' },
  { value: 'heritage', label: 'Heritage Auctions' },
  { value: 'pristine', label: 'Pristine Auction' },
  { value: 'rea', label: 'REA' },
  { value: 'cardhobby', label: 'Card Hobby' },
];

const itemTypes = [
  { value: 'cards', label: 'Trading Cards' },
  { value: 'memorabilia', label: 'Memorabilia' },
  { value: 'autographs', label: 'Autographs' },
];

const sports = [
  { value: 'BASKETBALL', label: 'Basketball' },
  { value: 'BASEBALL', label: 'Baseball' },
  { value: 'FOOTBALL', label: 'Football' },
  { value: 'HOCKEY', label: 'Hockey' },
  { value: 'SOCCER', label: 'Soccer' },
  { value: 'GOLF', label: 'Golf' },
  { value: 'BOXING', label: 'Boxing' },
  { value: 'RACING', label: 'Racing' },
  { value: 'OTHER', label: 'Other' },
];

const sortOptions = [
  { value: 'endTime', label: 'Ending Soon' },
  { value: 'bestValue', label: 'Best Value' },
  { value: 'priceLow', label: 'Price: Low to High' },
  { value: 'priceHigh', label: 'Price: High to Low' },
  { value: 'bidCount', label: 'Most Bids' },
  { value: 'recent', label: 'Recently Added' },
];

interface FilterBarProps {
  totalFiltered: number;
  totalItems: number;
  isLoadingMore?: boolean;
  loadingProgress?: number;
}

export function FilterBar({ totalFiltered, totalItems, isLoadingMore, loadingProgress }: FilterBarProps) {
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

  const { openAISearch } = useAISearch();
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false);

  const activeFilters = [
    auctionHouse && { key: 'house', label: auctionHouses.find(h => h.value === auctionHouse)?.label || auctionHouse, onRemove: () => setAuctionHouse('') },
    sport && { key: 'sport', label: sports.find(s => s.value === sport)?.label || sport, onRemove: () => setSport('') },
    itemType && { key: 'type', label: itemTypes.find(t => t.value === itemType)?.label || itemType, onRemove: () => setItemType('') },
    minPrice && { key: 'min', label: `Min: $${minPrice}`, onRemove: () => setMinPrice('') },
    maxPrice && { key: 'max', label: `Max: $${maxPrice}`, onRemove: () => setMaxPrice('') },
    searchInput && { key: 'search', label: `"${searchInput}"`, onRemove: () => setSearchInput('') },
  ].filter(Boolean) as { key: string; label: string; onRemove: () => void }[];

  const hasActiveFilters = activeFilters.length > 0;

  return (
    <div className="space-y-3">
      {/* Mobile: Redesigned filter bar */}
      <div className="md:hidden space-y-3">
        {/* Row 1: AI Search Button - prominent and full width */}
        <button
          onClick={openAISearch}
          className="w-full px-4 py-3 bg-gradient-to-r from-accent/20 to-purple-500/20 border border-accent/30 rounded-xl text-left flex items-center gap-3 active:scale-[0.98] transition-transform"
        >
          <div className="w-10 h-10 rounded-full bg-accent/20 flex items-center justify-center">
            <SparklesIcon className="w-5 h-5 text-accent" />
          </div>
          <div className="flex-1">
            <p className="text-sm font-medium text-text">AI Search</p>
            <p className="text-xs text-muted">Describe what you're looking for...</p>
          </div>
          <ChevronRightIcon className="w-5 h-5 text-muted" />
        </button>

        {/* Row 2: Search input with filter button */}
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <Input
              type="text"
              placeholder="Search items..."
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="pl-9 bg-panel border-border text-text placeholder:text-muted h-10"
            />
            {searchInput && (
              <button
                onClick={() => setSearchInput('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-text"
              >
                <XIcon className="w-4 h-4" />
              </button>
            )}
          </div>

          <Sheet open={mobileFiltersOpen} onOpenChange={setMobileFiltersOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="relative h-10 w-10 shrink-0">
                <FilterIcon />
                {(minPrice || maxPrice || itemType) && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 bg-accent text-[10px] text-white rounded-full flex items-center justify-center">
                    {[minPrice, maxPrice, itemType].filter(Boolean).length}
                  </span>
                )}
              </Button>
            </SheetTrigger>
            <SheetContent side="bottom" className="h-[70vh] bg-panel border-border rounded-t-2xl">
              <SheetHeader>
                <SheetTitle className="text-text flex items-center justify-between">
                  <span>More Filters</span>
                  {hasActiveFilters && (
                    <Button variant="ghost" size="sm" onClick={clearFilters}>
                      Clear All
                    </Button>
                  )}
                </SheetTitle>
              </SheetHeader>

              <div className="mt-6 space-y-6 overflow-y-auto pb-safe">
                {/* Sort By */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-2">Sort By</label>
                  <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
                    <SelectTrigger className="w-full bg-panel-2 border-border text-text">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-panel border-border">
                      {sortOptions.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value} className="text-text">
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Item Type */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-2">Item Type</label>
                  <Select value={itemType || 'all'} onValueChange={(v) => setItemType(v === 'all' ? '' : v as ItemTypeFilter)}>
                    <SelectTrigger className="w-full bg-panel-2 border-border text-text">
                      <SelectValue placeholder="All Types" />
                    </SelectTrigger>
                    <SelectContent className="bg-panel border-border">
                      <SelectItem value="all" className="text-text">All Types</SelectItem>
                      {itemTypes.map((t) => (
                        <SelectItem key={t.value} value={t.value} className="text-text">
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Price Range */}
                <div className="space-y-2">
                  <label className="text-sm font-medium text-text-2">Price Range</label>
                  <div className="flex items-center gap-2">
                    <div className="relative flex-1">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">$</span>
                      <Input
                        type="number"
                        placeholder="Min"
                        value={minPrice}
                        onChange={(e) => setMinPrice(e.target.value)}
                        className="pl-7 bg-panel-2 border-border text-text"
                      />
                    </div>
                    <span className="text-muted">-</span>
                    <div className="relative flex-1">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted">$</span>
                      <Input
                        type="number"
                        placeholder="Max"
                        value={maxPrice}
                        onChange={(e) => setMaxPrice(e.target.value)}
                        className="pl-7 bg-panel-2 border-border text-text"
                      />
                    </div>
                  </div>
                </div>

                {/* Apply Button */}
                <Button
                  className="w-full mt-4"
                  onClick={() => setMobileFiltersOpen(false)}
                >
                  Show {totalFiltered.toLocaleString()} Results
                </Button>
              </div>
            </SheetContent>
          </Sheet>
        </div>

        {/* Row 3: Auction House quick filters - horizontal scroll */}
        <div className="relative -mx-4 px-4">
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            <button
              onClick={() => setAuctionHouse('')}
              className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                !auctionHouse
                  ? 'bg-accent text-white'
                  : 'bg-panel-2 text-text-2 border border-border hover:border-accent/50'
              }`}
            >
              All
            </button>
            {auctionHouses.map((h) => (
              <button
                key={h.value}
                onClick={() => setAuctionHouse(auctionHouse === h.value ? '' : h.value)}
                className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  auctionHouse === h.value
                    ? 'bg-accent text-white'
                    : 'bg-panel-2 text-text-2 border border-border hover:border-accent/50'
                }`}
              >
                {h.label}
              </button>
            ))}
          </div>
        </div>

        {/* Row 4: Sport quick filters - horizontal scroll */}
        <div className="relative -mx-4 px-4">
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            <button
              onClick={() => setSport('')}
              className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                !sport
                  ? 'bg-purple-500 text-white'
                  : 'bg-panel-2 text-text-2 border border-border hover:border-purple-500/50'
              }`}
            >
              All Sports
            </button>
            {sports.map((s) => (
              <button
                key={s.value}
                onClick={() => setSport(sport === s.value ? '' : s.value as SportFilterType)}
                className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  sport === s.value
                    ? 'bg-purple-500 text-white'
                    : 'bg-panel-2 text-text-2 border border-border hover:border-purple-500/50'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>

        {/* Row 5: Sort dropdown and Clear All button */}
        <div className="flex items-center gap-2">
          <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
            <SelectTrigger className="flex-1 bg-panel border-border text-text h-10">
              <div className="flex items-center gap-2">
                <SortIcon className="w-4 h-4 text-muted" />
                <SelectValue />
              </div>
            </SelectTrigger>
            <SelectContent className="bg-panel border-border">
              {sortOptions.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-text">
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Clear All Filters button - visible when filters are active */}
          {hasActiveFilters && (
            <Button
              variant="outline"
              size="sm"
              onClick={clearFilters}
              className="h-10 px-3 shrink-0 text-red-400 border-red-400/30 hover:bg-red-400/10 hover:text-red-300"
            >
              <XIcon className="w-4 h-4 mr-1" />
              Clear All
            </Button>
          )}
        </div>
      </div>

      {/* Desktop: Full filter bar */}
      <div className="hidden md:flex items-center gap-3 flex-wrap">
        <div className="relative">
          <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <Input
            type="text"
            placeholder="Search items..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="pl-9 w-[200px] bg-panel border-border text-text placeholder:text-muted"
          />
        </div>

        <Select value={auctionHouse || 'all'} onValueChange={(v) => setAuctionHouse(v === 'all' ? '' : v)}>
          <SelectTrigger className="w-[180px] bg-panel border-border text-text">
            <SelectValue placeholder="All Auction Houses" />
          </SelectTrigger>
          <SelectContent className="bg-panel border-border">
            <SelectItem value="all" className="text-text">All Auction Houses</SelectItem>
            {auctionHouses.map((h) => (
              <SelectItem key={h.value} value={h.value} className="text-text">
                {h.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sport || 'all'} onValueChange={(v) => setSport(v === 'all' ? '' : v as SportFilterType)}>
          <SelectTrigger className="w-[140px] bg-panel border-border text-text">
            <SelectValue placeholder="All Sports" />
          </SelectTrigger>
          <SelectContent className="bg-panel border-border">
            <SelectItem value="all" className="text-text">All Sports</SelectItem>
            {sports.map((s) => (
              <SelectItem key={s.value} value={s.value} className="text-text">
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={itemType || 'all'} onValueChange={(v) => setItemType(v === 'all' ? '' : v as ItemTypeFilter)}>
          <SelectTrigger className="w-[150px] bg-panel border-border text-text">
            <SelectValue placeholder="All Types" />
          </SelectTrigger>
          <SelectContent className="bg-panel border-border">
            <SelectItem value="all" className="text-text">All Types</SelectItem>
            {itemTypes.map((t) => (
              <SelectItem key={t.value} value={t.value} className="text-text">
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v) => setSortBy(v as SortOption)}>
          <SelectTrigger className="w-[160px] bg-panel border-border text-text">
            <SelectValue />
          </SelectTrigger>
          <SelectContent className="bg-panel border-border">
            {sortOptions.map((opt) => (
              <SelectItem key={opt.value} value={opt.value} className="text-text">
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <span className="text-muted text-sm">$</span>
          <Input
            type="number"
            placeholder="Min"
            value={minPrice}
            onChange={(e) => setMinPrice(e.target.value)}
            className="w-20 bg-panel border-border text-text placeholder:text-muted"
          />
          <span className="text-muted">-</span>
          <Input
            type="number"
            placeholder="Max"
            value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            className="w-20 bg-panel border-border text-text placeholder:text-muted"
          />
        </div>

        {hasActiveFilters && (
          <Button
            variant="outline"
            size="sm"
            onClick={clearFilters}
            className="text-red-400 border-red-400/30 hover:bg-red-400/10 hover:text-red-300"
          >
            <XIcon className="w-4 h-4 mr-1" />
            Clear All
          </Button>
        )}
      </div>

      {/* Active Filter Chips */}
      <AnimatePresence>
        {hasActiveFilters && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 flex-wrap"
          >
            <span className="text-xs text-muted">Active:</span>
            {activeFilters.map((filter) => (
              <motion.div
                key={filter.key}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
              >
                <Badge
                  variant="secondary"
                  className="bg-accent/10 text-accent border-accent/20 hover:bg-accent/20 cursor-pointer gap-1 pr-1"
                  onClick={filter.onRemove}
                >
                  {filter.label}
                  <span className="ml-1 hover:bg-accent/30 rounded-full p-0.5">
                    <XIcon className="w-3 h-3" />
                  </span>
                </Badge>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results count with loading indicator */}
      <div className="flex items-center gap-2">
        <p className="text-sm text-text-2">
          {totalFiltered.toLocaleString()} of {totalItems.toLocaleString()} items
          {hasActiveFilters && ' (filtered)'}
        </p>
        {isLoadingMore && (
          <span className="flex items-center gap-1.5 text-xs text-accent">
            <LoadingSpinner className="w-3 h-3" />
            Loading more ({loadingProgress}%)
          </span>
        )}
      </div>
    </div>
  );
}

function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
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

function FilterIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
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

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
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

function SortIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
    </svg>
  );
}
