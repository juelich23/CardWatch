import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Connections | CardWatch',
};

export default function ConnectionsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
