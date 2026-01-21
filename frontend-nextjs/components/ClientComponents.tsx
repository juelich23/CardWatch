'use client';

import dynamic from 'next/dynamic';

// Dynamically import heavy components - only loaded when needed
export const CommandPalette = dynamic(
  () => import('./CommandPalette').then(mod => ({ default: mod.CommandPalette })),
  {
    ssr: false,
    loading: () => null,
  }
);

export const AISearchWrapper = dynamic(
  () => import('./AISearchWrapper').then(mod => ({ default: mod.AISearchWrapper })),
  {
    ssr: false,
    loading: () => null,
  }
);
