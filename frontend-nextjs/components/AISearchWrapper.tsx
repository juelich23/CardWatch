'use client';

import { useAISearch } from '@/lib/providers/AISearchProvider';
import { AISearchModal } from './AISearchModal';

export function AISearchWrapper() {
  const { isOpen, closeAISearch } = useAISearch();
  return <AISearchModal isOpen={isOpen} onClose={closeAISearch} />;
}
