'use client';

export function AuctionCardSkeleton() {
  return (
    <div className="bg-panel border border-border rounded-lg overflow-hidden animate-pulse">
      {/* Image placeholder */}
      <div className="w-full h-72 bg-panel-2" />

      {/* Content */}
      <div className="p-4">
        {/* Lot number */}
        <div className="h-3 w-16 bg-panel-2 rounded mb-2" />

        {/* Title */}
        <div className="h-4 w-full bg-panel-2 rounded mb-1" />
        <div className="h-4 w-3/4 bg-panel-2 rounded mb-4" />

        {/* Price */}
        <div className="h-8 w-24 bg-panel-2 rounded mb-2" />
        <div className="h-3 w-32 bg-panel-2 rounded mb-4" />

        {/* Market value badge */}
        <div className="h-6 w-28 bg-panel-2 rounded mb-4" />

        {/* Button */}
        <div className="h-10 w-full bg-panel-2 rounded" />
      </div>
    </div>
  );
}

export function AuctionGridSkeleton({ count = 20 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
      {Array.from({ length: count }).map((_, i) => (
        <AuctionCardSkeleton key={i} />
      ))}
    </div>
  );
}
