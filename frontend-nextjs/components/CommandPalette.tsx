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
import { Search, Heart, Filter, Clock, TrendingUp, Flame, X, LogOut, Sparkles } from 'lucide-react';
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
      icon: <Sparkles className="w-4 h-4" />,
      shortcut: '⌘⇧S',
      onSelect: () => openAISearch(),
      group: 'Navigation',
    },
    {
      id: 'browse',
      label: 'Browse Auctions',
      icon: <Search className="w-4 h-4" />,
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
      icon: <Heart className="w-4 h-4" />,
      shortcut: '⌘W',
      onSelect: () => router.push('/watchlist'),
      group: 'Navigation',
    },
  ];

  const filterItems: CommandItemType[] = [
    {
      id: 'filter-cards',
      label: 'Filter: Cards Only',
      icon: <Filter className="w-4 h-4" />,
      onSelect: () => {
        setItemType('cards');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-memorabilia',
      label: 'Filter: Memorabilia Only',
      icon: <Filter className="w-4 h-4" />,
      onSelect: () => {
        setItemType('memorabilia');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-autographs',
      label: 'Filter: Autographs Only',
      icon: <Filter className="w-4 h-4" />,
      onSelect: () => {
        setItemType('autographs');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-ending-soon',
      label: 'Sort: Ending Soon',
      icon: <Clock className="w-4 h-4" />,
      onSelect: () => {
        setSortBy('endTime');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-best-value',
      label: 'Sort: Best Value',
      icon: <TrendingUp className="w-4 h-4" />,
      onSelect: () => {
        setSortBy('bestValue');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-most-bids',
      label: 'Sort: Most Bids',
      icon: <Flame className="w-4 h-4" />,
      onSelect: () => {
        setSortBy('bidCount');
        router.push('/');
      },
      group: 'Quick Filters',
    },
    {
      id: 'filter-clear',
      label: 'Clear All Filters',
      icon: <X className="w-4 h-4" />,
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
          icon: <LogOut className="w-4 h-4" />,
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

