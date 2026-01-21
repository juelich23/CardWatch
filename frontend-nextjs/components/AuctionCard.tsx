'use client';

import { AuctionItem } from '@/lib/types';
import { MarketValueBadge } from './MarketValueBadge';
import { useMutation } from '@apollo/client/react';
import { TOGGLE_WATCH } from '@/lib/graphql/queries';
import { useAuth } from '@/lib/providers/AuthProvider';
import { useState } from 'react';
import Image from 'next/image';
import { motion } from 'framer-motion';
import { toast } from 'sonner';

interface AuctionCardProps {
  item: AuctionItem;
}

export function AuctionCard({ item }: AuctionCardProps) {
  const { user } = useAuth();
  const [isWatched, setIsWatched] = useState(item.isWatched || false);
  const [isToggling, setIsToggling] = useState(false);
  const [imageError, setImageError] = useState(false);

  const [toggleWatch] = useMutation<{ toggleWatch: { success: boolean } }>(TOGGLE_WATCH, {
    onCompleted: (data) => {
      if (data?.toggleWatch?.success) {
        setIsWatched(!isWatched);
        toast.success(isWatched ? 'Removed from watchlist' : 'Added to watchlist');
      }
      setIsToggling(false);
    },
    onError: () => {
      toast.error('Failed to update watchlist');
      setIsToggling(false);
    },
  });

  const handleToggleWatch = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!user) {
      toast.error('Please sign in to add items to your watchlist');
      return;
    }
    if (isToggling) return;
    setIsToggling(true);
    await toggleWatch({ variables: { itemId: item.id } });
  };

  const formatCurrency = (amount?: number) => {
    if (amount === undefined || amount === null) return 'N/A';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatTimeRemaining = (endTime?: string) => {
    if (!endTime) return 'Unknown';
    const utcEndTime = endTime.includes('Z') || endTime.includes('+') ? endTime : endTime + 'Z';
    const end = new Date(utcEndTime);
    const now = new Date();
    const diff = end.getTime() - now.getTime();

    if (diff < 0) return 'Ended';

    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const isEndingSoon = () => {
    if (!item.endTime) return false;
    const utcEndTime = item.endTime.includes('Z') || item.endTime.includes('+') ? item.endTime : item.endTime + 'Z';
    const end = new Date(utcEndTime);
    const now = new Date();
    const diff = end.getTime() - now.getTime();
    return diff > 0 && diff < 1000 * 60 * 60 * 24; // Less than 24 hours
  };

  const auctionHouseBadges: Record<string, { bg: string; text: string }> = {
    goldin: { bg: 'bg-yellow-500', text: 'Goldin' },
    fanatics: { bg: 'bg-red-600', text: 'Fanatics' },
    pristine: { bg: 'bg-blue-500', text: 'Pristine' },
    rea: { bg: 'bg-amber-700', text: 'REA' },
    heritage: { bg: 'bg-blue-800', text: 'Heritage' },
    cardhobby: { bg: 'bg-purple-600', text: 'Card Hobby' },
  };

  const badge = auctionHouseBadges[item.auctionHouse] || { bg: 'bg-muted', text: item.auctionHouse };

  // Format auction house name for display
  const getAuctionHouseDisplayName = () => {
    const names: Record<string, string> = {
      goldin: 'Goldin',
      fanatics: 'Fanatics',
      pristine: 'Pristine',
      rea: 'REA',
      heritage: 'Heritage',
      cardhobby: 'Card Hobby',
    };
    return names[item.auctionHouse] || item.auctionHouse;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.15 }}
      className="bg-panel border rounded-lg sm:rounded-xl overflow-hidden transition-all flex flex-col border-border hover:border-accent/50"
    >
      {/* Image Container - Responsive height */}
      <div className="relative bg-panel-2">
        {/* Action buttons - Compact on mobile for 2-col grid */}
        <div className="absolute top-1.5 sm:top-2 right-1.5 sm:right-2 z-10 flex gap-1 sm:gap-2">
          {/* Watchlist button */}
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={handleToggleWatch}
            disabled={isToggling}
            className={`w-7 h-7 sm:w-9 sm:h-9 rounded-full flex items-center justify-center transition-all shadow-lg ${
              isWatched
                ? 'bg-red-500 text-white'
                : 'bg-panel/90 backdrop-blur-sm border border-border hover:border-red-400 text-text-2 hover:text-red-400'
            } ${isToggling ? 'opacity-50' : ''}`}
            aria-label={isWatched ? 'Remove from watchlist' : 'Add to watchlist'}
          >
            <svg
              className="w-3.5 h-3.5 sm:w-4 sm:h-4"
              fill={isWatched ? 'currentColor' : 'none'}
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"
              />
            </svg>
          </motion.button>
        </div>

        {/* Auction house badge - Smaller on mobile */}
        <div className="absolute top-1.5 sm:top-2 left-1.5 sm:left-2 z-10">
          <div className={`${badge.bg} text-white text-[10px] sm:text-xs font-semibold px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-md shadow-lg`}>
            {badge.text}
          </div>
        </div>

        {/* Ending soon indicator - Smaller on mobile */}
        {isEndingSoon() && (
          <div className="absolute bottom-1.5 sm:bottom-2 left-1.5 sm:left-2 z-10">
            <div className="bg-red-500/90 text-white text-[10px] sm:text-xs font-semibold px-1.5 sm:px-2.5 py-0.5 sm:py-1 rounded-md flex items-center gap-0.5 sm:gap-1 animate-pulse">
              <ClockIcon className="w-2.5 h-2.5 sm:w-3 sm:h-3" />
              <span className="hidden sm:inline">Ending </span>Soon
            </div>
          </div>
        )}

        {/* Image - Compact on mobile for 2-col grid */}
        {item.imageUrl && !imageError ? (
          <div className="w-full h-32 sm:h-44 md:h-52 relative">
            <Image
              src={item.imageUrl}
              alt={item.title}
              fill
              sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
              className="object-contain p-2 sm:p-4"
              loading="lazy"
              unoptimized
              onError={() => setImageError(true)}
            />
          </div>
        ) : (
          <div className="w-full h-32 sm:h-44 md:h-52 bg-panel-2 flex flex-col items-center justify-center p-4">
            <svg className="w-8 h-8 sm:w-12 sm:h-12 text-muted mb-1 sm:mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <span className="text-muted text-xs sm:text-sm">No image</span>
          </div>
        )}
      </div>

      {/* Content - Compact on mobile */}
      <div className="p-2 sm:p-4 flex flex-col flex-1">
        {/* Lot Number & Grading - Hidden on very small screens */}
        <div className="hidden sm:flex items-center gap-2 mb-1.5 text-xs">
          {item.lotNumber && (
            <span className="text-muted">Lot #{item.lotNumber}</span>
          )}
          {item.gradingCompany && item.grade && (
            <span className="bg-accent/10 text-accent px-1.5 py-0.5 rounded font-medium">
              {item.gradingCompany} {item.grade}
            </span>
          )}
        </div>

        {/* Grading badge on mobile - smaller */}
        {item.gradingCompany && item.grade && (
          <div className="sm:hidden mb-1">
            <span className="bg-accent/10 text-accent px-1 py-0.5 rounded text-[10px] font-medium">
              {item.gradingCompany} {item.grade}
            </span>
          </div>
        )}

        {/* Title */}
        <h3 className="font-medium text-text line-clamp-2 mb-2 sm:mb-3 text-xs sm:text-sm leading-snug min-h-[2rem] sm:min-h-[2.5rem]">
          {item.title}
        </h3>

        {/* Price */}
        <div className="mb-1.5 sm:mb-2">
          <div className="text-base sm:text-xl md:text-2xl font-bold text-text">
            {formatCurrency(item.currentBid)}
          </div>
          <div className="text-[10px] sm:text-xs text-text-2 mt-0.5 sm:mt-1 flex items-center gap-1 sm:gap-2 flex-wrap">
            <span>{item.bidCount} {item.bidCount === 1 ? 'bid' : 'bids'}</span>
            <span className="text-border hidden sm:inline">·</span>
            <span className={`${isEndingSoon() ? 'text-red-400 font-medium' : ''}`}>
              {formatTimeRemaining(item.endTime)}
            </span>
          </div>
        </div>

        {/* Market Value - Smaller on mobile */}
        <div className="mb-2 sm:mb-3 min-h-[1.25rem] sm:min-h-[1.5rem]">
          <MarketValueBadge
            itemId={item.id}
            currentBid={item.currentBid}
            marketValueLow={item.marketValueLow}
            marketValueHigh={item.marketValueHigh}
            marketValueAvg={item.marketValueAvg}
            marketValueConfidence={item.marketValueConfidence}
          />
        </div>

        {/* Action */}
        <div className="mt-auto">
          {item.itemUrl && (
            <motion.a
              whileTap={{ scale: 0.98 }}
              href={item.itemUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full py-2 sm:py-2.5 px-2 sm:px-4 bg-accent hover:bg-accent/80 text-white text-xs sm:text-sm font-medium rounded-lg transition-colors min-h-[36px] sm:min-h-[44px] flex items-center justify-center gap-1.5"
            >
              View on {getAuctionHouseDisplayName()}
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </motion.a>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
