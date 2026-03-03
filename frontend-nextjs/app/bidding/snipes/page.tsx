'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { biddingAPI } from '@/lib/api/bidding';
import type { GixenSnipe } from '@/lib/types/bidding';
import { statusColor } from '@/lib/formatters';

const STATUS_TABS = [
  { value: '', label: 'All' },
  { value: 'pending', label: 'Pending' },
  { value: 'submitted', label: 'Submitted' },
  { value: 'active', label: 'Active' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
  { value: 'error', label: 'Error' },
];

export default function SnipesPage() {
  const [snipes, setSnipes] = useState<GixenSnipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState('');
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const loadSnipes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await biddingAPI.listSnipes({
        status: statusFilter || undefined,
        limit: 100,
      });
      setSnipes(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load snipes');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    loadSnipes();
  }, [loadSnipes]);

  const handleCancel = async (id: number) => {
    if (!confirm('Cancel this snipe?')) return;
    setCancellingId(id);
    try {
      await biddingAPI.cancelSnipe(id);
      loadSnipes();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to cancel');
    } finally {
      setCancellingId(null);
    }
  };

  const canCancel = (status: string) => ['pending', 'submitted', 'active'].includes(status);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-text">Snipe History</h1>
        <Button variant="outline" onClick={loadSnipes} disabled={loading}>
          {loading ? 'Loading...' : 'Refresh'}
        </Button>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {/* Status Filters */}
      <Tabs value={statusFilter} onValueChange={setStatusFilter} className="mb-6">
        <TabsList>
          {STATUS_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Snipes Table */}
      {loading && snipes.length === 0 ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 bg-panel rounded-lg animate-pulse" />
          ))}
        </div>
      ) : snipes.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-text-2">No snipes found{statusFilter ? ` with status "${statusFilter}"` : ''}.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {snipes.map((snipe) => (
            <Card key={snipe.id}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-center gap-4">
                  {snipe.item_image_url && (
                    <img
                      src={snipe.item_image_url}
                      alt=""
                      className="w-16 h-16 rounded object-cover shrink-0"
                    />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {snipe.item_title || snipe.ebay_item_id}
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-text-2">
                      <span>Max bid: ${snipe.max_bid.toFixed(2)}</span>
                      {snipe.current_bid_at_snipe != null && (
                        <span>Bid at snipe: ${snipe.current_bid_at_snipe.toFixed(2)}</span>
                      )}
                      <span>Offset: {snipe.bid_offset_seconds}s</span>
                      {snipe.rule_name && <span>Rule: {snipe.rule_name}</span>}
                      <span>eBay: {snipe.ebay_item_id}</span>
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-text-2">
                      <span>Created: {formatDate(snipe.created_at)}</span>
                      {snipe.item_end_time && <span>Ends: {formatDate(snipe.item_end_time)}</span>}
                      {snipe.submitted_at && <span>Submitted: {formatDate(snipe.submitted_at)}</span>}
                    </div>
                    {snipe.gixen_message && (
                      <p className="text-xs text-text-2 mt-1 truncate">
                        Gixen: {snipe.gixen_message}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <Badge className={statusColor(snipe.status)}>
                      {snipe.status}
                    </Badge>
                    {snipe.final_price != null && (
                      <span className="text-sm font-medium text-text">
                        ${snipe.final_price.toFixed(2)}
                      </span>
                    )}
                    {canCancel(snipe.status) && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="text-red-400 hover:text-red-300"
                        onClick={() => handleCancel(snipe.id)}
                        disabled={cancellingId === snipe.id}
                      >
                        {cancellingId === snipe.id ? 'Cancelling...' : 'Cancel'}
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
