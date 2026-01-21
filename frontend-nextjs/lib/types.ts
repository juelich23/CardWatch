export interface AuctionItem {
  id: number;
  title: string;
  description?: string;
  currentBid?: number;
  startingBid?: number;
  bidCount: number;
  endTime?: string;
  imageUrl?: string;
  itemUrl?: string;
  auctionHouse: string;
  lotNumber?: string;
  gradingCompany?: string;
  grade?: string;
  certNumber?: string;
  category?: string;
  sport?: string;
  status: string;
  isWatched: boolean;
  altPriceEstimate?: number;
  // Market value estimate (cached from LLM)
  marketValueLow?: number;
  marketValueHigh?: number;
  marketValueAvg?: number;
  marketValueConfidence?: string;
}

export type SportFilter =
  | 'BASKETBALL'
  | 'BASEBALL'
  | 'FOOTBALL'
  | 'HOCKEY'
  | 'SOCCER'
  | 'GOLF'
  | 'BOXING'
  | 'RACING'
  | 'OTHER';

export interface PaginatedAuctionItems {
  items: AuctionItem[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}

export interface MarketValueEstimate {
  estimatedLow?: number;
  estimatedHigh?: number;
  estimatedAverage?: number;
  confidence: string;
  notes: string;
}
