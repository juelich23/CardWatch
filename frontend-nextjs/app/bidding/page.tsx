'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { biddingAPI } from '@/lib/api/bidding';
import type { SnipeStats, GixenSnipe, GixenCredentialStatus } from '@/lib/types/bidding';

export default function BiddingDashboard() {
  const [stats, setStats] = useState<SnipeStats | null>(null);
  const [recentSnipes, setRecentSnipes] = useState<GixenSnipe[]>([]);
  const [credStatus, setCredStatus] = useState<GixenCredentialStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const [statsData, snipesData, credData] = await Promise.all([
        biddingAPI.getSnipeStats(),
        biddingAPI.listSnipes({ limit: 10 }),
        biddingAPI.getGixenCredentialStatus(),
      ]);
      setStats(statsData);
      setRecentSnipes(snipesData);
      setCredStatus(credData);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAction = async (action: string) => {
    setActionLoading(action);
    try {
      if (action === 'run-rules') await biddingAPI.runRules();
      else if (action === 'sync-gixen') await biddingAPI.syncGixen();
      else if (action === 'submit-pending') await biddingAPI.submitPending();
      // Refresh data after action
      setTimeout(loadData, 2000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Action failed');
    } finally {
      setActionLoading(null);
    }
  };

  const statusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-500/20 text-yellow-400',
      submitted: 'bg-blue-500/20 text-blue-400',
      active: 'bg-cyan-500/20 text-cyan-400',
      won: 'bg-green-500/20 text-green-400',
      lost: 'bg-red-500/20 text-red-400',
      error: 'bg-red-500/20 text-red-400',
      cancelled: 'bg-gray-500/20 text-gray-400',
      expired: 'bg-gray-500/20 text-gray-400',
    };
    return colors[status] || 'bg-gray-500/20 text-gray-400';
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-text mb-6">Bidding Dashboard</h1>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-24 bg-panel rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-text mb-6">Bidding Dashboard</h1>
        <Card>
          <CardContent className="pt-6">
            <p className="text-red-400">{error}</p>
            <p className="text-text-2 mt-2">Please sign in to access bidding features.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-text">Bidding Dashboard</h1>
        <div className="flex items-center gap-2">
          {credStatus && !credStatus.has_credentials && (
            <Link href="/bidding/settings">
              <Badge variant="outline" className="text-yellow-400 border-yellow-400/30">
                Setup Gixen
              </Badge>
            </Link>
          )}
          {credStatus?.has_credentials && credStatus.is_valid === false && (
            <Link href="/bidding/settings">
              <Badge variant="outline" className="text-red-400 border-red-400/30">
                Invalid Credentials
              </Badge>
            </Link>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Total Snipes</p>
              <p className="text-2xl font-bold text-text">{stats.total}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Active</p>
              <p className="text-2xl font-bold text-cyan-400">
                {stats.pending + stats.submitted + stats.active}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Won</p>
              <p className="text-2xl font-bold text-green-400">{stats.won}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Win Rate</p>
              <p className="text-2xl font-bold text-text">
                {stats.win_rate !== null ? `${stats.win_rate.toFixed(1)}%` : '--'}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Pending</p>
              <p className="text-2xl font-bold text-yellow-400">{stats.pending}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Lost</p>
              <p className="text-2xl font-bold text-red-400">{stats.lost}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Errors</p>
              <p className="text-2xl font-bold text-red-400">{stats.error}</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4 pb-4">
              <p className="text-sm text-text-2">Total Spent</p>
              <p className="text-2xl font-bold text-text">${stats.total_spent.toFixed(2)}</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-3 mb-8">
        <Button
          onClick={() => handleAction('run-rules')}
          disabled={actionLoading !== null}
          variant="outline"
        >
          {actionLoading === 'run-rules' ? 'Running...' : 'Run Rules'}
        </Button>
        <Button
          onClick={() => handleAction('submit-pending')}
          disabled={actionLoading !== null}
          variant="outline"
        >
          {actionLoading === 'submit-pending' ? 'Submitting...' : 'Submit Pending'}
        </Button>
        <Button
          onClick={() => handleAction('sync-gixen')}
          disabled={actionLoading !== null}
          variant="outline"
        >
          {actionLoading === 'sync-gixen' ? 'Syncing...' : 'Sync Gixen'}
        </Button>
        <div className="flex-1" />
        <Link href="/bidding/rules">
          <Button variant="outline">Manage Rules</Button>
        </Link>
        <Link href="/bidding/snipes">
          <Button variant="outline">View Snipes</Button>
        </Link>
        <Link href="/bidding/settings">
          <Button variant="outline">Settings</Button>
        </Link>
      </div>

      {error && (
        <p className="text-red-400 text-sm mb-4">{error}</p>
      )}

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Recent Snipes</CardTitle>
        </CardHeader>
        <CardContent>
          {recentSnipes.length === 0 ? (
            <p className="text-text-2 text-sm">No snipes yet. Create a bidding rule to get started.</p>
          ) : (
            <div className="space-y-3">
              {recentSnipes.map((snipe) => (
                <div
                  key={snipe.id}
                  className="flex items-center gap-3 p-3 rounded-lg bg-panel-2/50"
                >
                  {snipe.item_image_url && (
                    <img
                      src={snipe.item_image_url}
                      alt=""
                      className="w-12 h-12 rounded object-cover"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-text truncate">
                      {snipe.item_title || snipe.ebay_item_id}
                    </p>
                    <p className="text-xs text-text-2">
                      Max bid: ${snipe.max_bid.toFixed(2)}
                      {snipe.rule_name && ` | Rule: ${snipe.rule_name}`}
                    </p>
                  </div>
                  <Badge className={statusColor(snipe.status)}>
                    {snipe.status}
                  </Badge>
                  {snipe.final_price && (
                    <span className="text-sm text-text-2">${snipe.final_price.toFixed(2)}</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
