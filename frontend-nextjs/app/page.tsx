import { Suspense } from 'react';
import { AuctionList } from '@/components/AuctionList';
import { AuctionGridSkeleton } from '@/components/AuctionCardSkeleton';

function AuctionListFallback() {
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-text">Auction Items</h1>
        <p className="text-text-2 mt-2">Loading items...</p>
      </div>
      <AuctionGridSkeleton count={20} />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<AuctionListFallback />}>
      <AuctionList />
    </Suspense>
  );
}
