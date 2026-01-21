'use client';

import { createContext, useContext, useState, ReactNode, useCallback } from 'react';

type SortOption = 'endTime' | 'priceLow' | 'priceHigh' | 'bidCount' | 'recent' | 'bestValue';
type ItemTypeFilter = '' | 'cards' | 'memorabilia' | 'autographs';
type SportFilterType = '' | 'BASKETBALL' | 'BASEBALL' | 'FOOTBALL' | 'HOCKEY' | 'SOCCER' | 'GOLF' | 'BOXING' | 'RACING' | 'OTHER';

interface FilterContextType {
  // Filter values
  searchInput: string;
  auctionHouse: string;
  sortBy: SortOption;
  minPrice: string;
  maxPrice: string;
  itemType: ItemTypeFilter;
  sport: SportFilterType;

  // Setters
  setSearchInput: (value: string) => void;
  setAuctionHouse: (value: string) => void;
  setSortBy: (value: SortOption) => void;
  setMinPrice: (value: string) => void;
  setMaxPrice: (value: string) => void;
  setItemType: (value: ItemTypeFilter) => void;
  setSport: (value: SportFilterType) => void;

  // Utility functions
  clearFilters: () => void;
  applyFilters: (filters: Partial<FilterState>) => void;
}

interface FilterState {
  searchInput: string;
  auctionHouse: string;
  sortBy: SortOption;
  minPrice: string;
  maxPrice: string;
  itemType: ItemTypeFilter;
  sport: SportFilterType;
}

const FilterContext = createContext<FilterContextType | undefined>(undefined);

export function FilterProvider({ children }: { children: ReactNode }) {
  const [searchInput, setSearchInput] = useState('');
  const [auctionHouse, setAuctionHouse] = useState('');
  const [sortBy, setSortBy] = useState<SortOption>('priceHigh');
  const [minPrice, setMinPrice] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [itemType, setItemType] = useState<ItemTypeFilter>('');
  const [sport, setSport] = useState<SportFilterType>('');

  const clearFilters = useCallback(() => {
    setSearchInput('');
    setAuctionHouse('');
    setSortBy('priceHigh');
    setMinPrice('');
    setMaxPrice('');
    setItemType('');
    setSport('');
  }, []);

  const applyFilters = useCallback((filters: Partial<FilterState>) => {
    if (filters.searchInput !== undefined) setSearchInput(filters.searchInput);
    if (filters.auctionHouse !== undefined) setAuctionHouse(filters.auctionHouse);
    if (filters.sortBy !== undefined) setSortBy(filters.sortBy);
    if (filters.minPrice !== undefined) setMinPrice(filters.minPrice);
    if (filters.maxPrice !== undefined) setMaxPrice(filters.maxPrice);
    if (filters.itemType !== undefined) setItemType(filters.itemType);
    if (filters.sport !== undefined) setSport(filters.sport);
  }, []);

  return (
    <FilterContext.Provider
      value={{
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
        applyFilters,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters() {
  const context = useContext(FilterContext);
  if (context === undefined) {
    throw new Error('useFilters must be used within a FilterProvider');
  }
  return context;
}

// Export types for use elsewhere
export type { SortOption, ItemTypeFilter, SportFilterType, FilterState };
