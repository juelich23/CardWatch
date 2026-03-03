import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Snipes | CardWatch',
};

export default function SnipesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
