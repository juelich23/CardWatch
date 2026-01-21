'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command';
import { useAuth } from '@/lib/providers/AuthProvider';
import { useFilters } from '@/lib/providers/FilterProvider';
import { useAISearch } from '@/lib/providers/AISearchProvider';

interface CommandItemType {
  id: string;
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  onSelect: () => void;
  group: string;
}

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();
  const { user, logout } = useAuth();
  const {
    setAuctionHouse,
    setItemType,
    setSortBy,
    clearFilters,
  } = useFilters();
  const { openAISearch } = useAISearch();

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, []);

  const runCommand = useCallback((command: () => void) => {
    setOpen(false);
    command();
  }, []);

  const navigationItems: CommandItemType[] = [
    {
      id: 'ai-search',
      label: 'AI Search',
      icon: <SparklesIcon />,
      shortcut: '⌘⇧S',
      onSelect: () => openAISearch(),
      group: 'Navigation',
    },
    {
      id: 'browse',
      label: 'Browse Auctions',
      icon: <SearchIcon />,
      shortcut: '⌘B',
      onSelect: () => {
        clearFilters();
        router.push('/');
      },
      group: 'Navigation',
    },
    {
      id: 'watchlist',
      label: 'Watchlist',
      icon: <HeartIcon />,
      shortcut: '⌘W',
      onSelect: () => router.push('/watchlist'),
      group: 'Navigation',
    },
  ];

  const filterItems: CommandItemType[] = [
    {
      id: 'filter-cards',
      label: 'Filter: Cards Only',
      icon: <FilterIcon />,
      onSelect: () => {
        setItemType('cards');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-memorabilia',
      label: 'Filter: Memorabilia Only',
      icon: <FilterIcon />,
      onSelect: () => {
        setItemType('memorabilia');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-autographs',
      label: 'Filter: Autographs Only',
      icon: <FilterIcon />,
      onSelect: () => {
        setItemType('autographs');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-ending-soon',
      label: 'Sort: Ending Soon',
      icon: <ClockIcon />,
      onSelect: () => {
        setSortBy('endTime');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-best-value',
      label: 'Sort: Best Value',
      icon: <TrendingIcon />,
      onSelect: () => {
        setSortBy('bestValue');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-most-bids',
      label: 'Sort: Most Bids',
      icon: <FireIcon />,
      onSelect: () => {
        setSortBy('bidCount');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-clear',
      label: 'Clear All Filters',
      icon: <XIcon />,
      onSelect: () => {
        clearFilters();
        router.push('/');
      },
      group: 'Quick Filters',
    },
  ];

  const auctionHouseItems: CommandItemType[] = [
    {
      id: 'goldin',
      label: 'Goldin Auctions',
      icon: <span className="w-2 h-2 rounded-full bg-yellow-500" />,
      onSelect: () => {
        setAuctionHouse('goldin');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'fanatics',
      label: 'Fanatics Collect',
      icon: <span className="w-2 h-2 rounded-full bg-red-600" />,
      onSelect: () => {
        setAuctionHouse('fanatics');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'pristine',
      label: 'Pristine Auction',
      icon: <span className="w-2 h-2 rounded-full bg-blue-500" />,
      onSelect: () => {
        setAuctionHouse('pristine');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'rea',
      label: 'REA Marketplace',
      icon: <span className="w-2 h-2 rounded-full bg-amber-700" />,
      onSelect: () => {
        setAuctionHouse('rea');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'heritage',
      label: 'Heritage Auctions',
      icon: <span className="w-2 h-2 rounded-full bg-blue-800" />,
      onSelect: () => {
        setAuctionHouse('heritage');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'cardhobby',
      label: 'Card Hobby',
      icon: <span className="w-2 h-2 rounded-full bg-purple-600" />,
      onSelect: () => {
        setAuctionHouse('cardhobby');
        router.push('/');
      },
      group: 'Auction Houses',
    },
    {
      id: 'all-houses',
      label: 'All Auction Houses',
      icon: <span className="w-2 h-2 rounded-full bg-gray-500" />,
      onSelect: () => {
        setAuctionHouse('');
        router.push('/');
      },
      group: 'Auction Houses',
    },
  ];

  const accountItems: CommandItemType[] = user
    ? [
        {
          id: 'logout',
          label: 'Sign Out',
          icon: <LogoutIcon />,
          onSelect: () => logout(),
          group: 'Account',
        },
      ]
    : [];

  const themeItems: CommandItemType[] = [
    {
      id: 'theme-charcoal',
      label: 'Theme: Charcoal Blue',
      icon: <span className="w-2 h-2 rounded-full bg-blue-500" />,
      onSelect: () => document.documentElement.setAttribute('data-theme', 'charcoal-blue'),
      group: 'Appearance',
    },
    {
      id: 'theme-teal',
      label: 'Theme: Graphite Teal',
      icon: <span className="w-2 h-2 rounded-full bg-teal-500" />,
      onSelect: () => document.documentElement.setAttribute('data-theme', 'graphite-teal'),
      group: 'Appearance',
    },
    {
      id: 'theme-slate',
      label: 'Theme: Neutral Slate',
      icon: <span className="w-2 h-2 rounded-full bg-purple-500" />,
      onSelect: () => document.documentElement.setAttribute('data-theme', 'neutral-slate'),
      group: 'Appearance',
    },
  ];

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput
        placeholder="Type a command or search..."
        className="border-none focus:ring-0"
      />
      <CommandList className="max-h-[400px]">
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigation">
          {navigationItems.map((item) => (
            <CommandItem
              key={item.id}
              onSelect={() => runCommand(item.onSelect)}
              className="flex items-center gap-2 cursor-pointer"
            >
              <span className="text-muted">{item.icon}</span>
              <span>{item.label}</span>
              {item.shortcut && (
                <span className="ml-auto text-xs text-muted">{item.shortcut}</span>
              )}
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Quick Filters">
          {filterItems.map((item) => (
            <CommandItem
              key={item.id}
              onSelect={() => runCommand(item.onSelect)}
              className="flex items-center gap-2 cursor-pointer"
            >
              <span className="text-muted">{item.icon}</span>
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Auction Houses">
          {auctionHouseItems.map((item) => (
            <CommandItem
              key={item.id}
              onSelect={() => runCommand(item.onSelect)}
              className="flex items-center gap-2 cursor-pointer"
            >
              {item.icon}
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Appearance">
          {themeItems.map((item) => (
            <CommandItem
              key={item.id}
              onSelect={() => runCommand(item.onSelect)}
              className="flex items-center gap-2 cursor-pointer"
            >
              {item.icon}
              <span>{item.label}</span>
            </CommandItem>
          ))}
        </CommandGroup>

        {accountItems.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Account">
              {accountItems.map((item) => (
                <CommandItem
                  key={item.id}
                  onSelect={() => runCommand(item.onSelect)}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <span className="text-muted">{item.icon}</span>
                  <span>{item.label}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  );
}

// Icons
function SearchIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function HeartIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
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

function ClockIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function TrendingIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  );
}

function FireIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
    </svg>
  );
}

function SparklesIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
    </svg>
  );
}
