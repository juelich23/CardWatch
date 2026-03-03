import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Bidding Rules | CardWatch',
};

export default function RulesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
