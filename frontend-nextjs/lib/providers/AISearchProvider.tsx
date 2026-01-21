'use client';

import { createContext, useContext, useState, ReactNode, useCallback } from 'react';

interface AISearchContextType {
  isOpen: boolean;
  openAISearch: () => void;
  closeAISearch: () => void;
}

const AISearchContext = createContext<AISearchContextType | undefined>(undefined);

export function AISearchProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);

  const openAISearch = useCallback(() => setIsOpen(true), []);
  const closeAISearch = useCallback(() => setIsOpen(false), []);

  return (
    <AISearchContext.Provider value={{ isOpen, openAISearch, closeAISearch }}>
      {children}
    </AISearchContext.Provider>
  );
}

export function useAISearch() {
  const context = useContext(AISearchContext);
  if (context === undefined) {
    throw new Error('useAISearch must be used within an AISearchProvider');
  }
  return context;
}
