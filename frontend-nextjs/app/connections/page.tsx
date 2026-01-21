'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/providers/AuthProvider';
import { ConnectionCard } from '@/components/ConnectionCard';
import { credentialsAPI, CredentialStatus, AUCTION_HOUSES } from '@/lib/api/credentials';

export default function ConnectionsPage() {
  const { user } = useAuth();
  const router = useRouter();
  const [statuses, setStatuses] = useState<CredentialStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchStatuses = async () => {
    setLoading(true);
    try {
      const data = await credentialsAPI.getStatus();
      setStatuses(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load connections');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!mounted) return;

    if (!user) {
      router.push('/');
      return;
    }

    fetchStatuses();
  }, [user, mounted, router]);

  // Show minimal page during SSR
  if (!mounted) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-3xl mx-auto">
          <h1 className="text-2xl font-bold text-text mb-2">Auction House Connections</h1>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-text-2 text-center">Redirecting...</div>
      </div>
    );
  }

  const getStatusForHouse = (houseId: string) => {
    return statuses.find((s) => s.auction_house === houseId);
  };

  const connectedCount = statuses.filter((s) => s.has_credentials).length;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-text mb-2">Auction House Connections</h1>
          <p className="text-text-2">
            Connect your auction house accounts to enable bulk bidding across platforms.
            Your credentials are encrypted and stored securely.
          </p>
        </div>

        <div className="mb-6 flex items-center gap-4">
          <div className="bg-panel border border-border rounded-lg px-4 py-3">
            <span className="text-text-2 text-sm">Connected</span>
            <div className="text-2xl font-bold text-text">
              {connectedCount} / {AUCTION_HOUSES.length}
            </div>
          </div>
          <button
            onClick={fetchStatuses}
            disabled={loading}
            className="px-4 py-2 border border-border text-text-2 hover:text-text rounded-md transition-colors text-sm"
          >
            {loading ? 'Refreshing...' : 'Refresh Status'}
          </button>
        </div>

        {error && (
          <div className="mb-6 text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg p-4">
            {error}
          </div>
        )}

        <div className="grid gap-4">
          {AUCTION_HOUSES.map((house) => (
            <ConnectionCard
              key={house.id}
              auctionHouse={house}
              status={getStatusForHouse(house.id)}
              onUpdate={fetchStatuses}
            />
          ))}
        </div>

        <div className="mt-8 p-4 bg-panel border border-border rounded-lg">
          <h3 className="font-medium text-text mb-2">Security Notice</h3>
          <p className="text-text-2 text-sm">
            Your auction house passwords are encrypted using AES-256 before being stored.
            We never have access to your plain-text passwords. Sessions are automatically
            managed and expire after 12 hours of inactivity.
          </p>
        </div>
      </div>
    </div>
  );
}
