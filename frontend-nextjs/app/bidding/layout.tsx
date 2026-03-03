import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Bidding | CardWatch',
};

export default function BiddingLayout({ children }: { children: React.ReactNode }) {
  return children;
}
