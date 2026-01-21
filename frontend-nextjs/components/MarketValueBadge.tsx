'use client';

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQuery } from '@apollo/client/react';
import { GET_MARKET_VALUE_ESTIMATE } from '@/lib/graphql/queries';
import { MarketValueEstimate } from '@/lib/types';
import dynamic from 'next/dynamic';

// Global event to close all estimate modals
const CLOSE_ALL_ESTIMATE_MODALS = 'close-all-estimate-modals';

// Dynamically import PriceHistoryChart - only loaded when tab is clicked
const PriceHistoryChart = dynamic(
  () => import('./PriceHistoryChart').then(mod => ({ default: mod.PriceHistoryChart })),
  {
    ssr: false,
    loading: () => (
      <div className="space-y-3 animate-pulse">
        <div className="flex justify-between">
          <div className="h-4 w-20 bg-panel-2 rounded" />
          <div className="h-4 w-20 bg-panel-2 rounded" />
          <div className="h-4 w-24 bg-panel-2 rounded" />
        </div>
        <div className="h-24 bg-panel-2 rounded" />
      </div>
    ),
  }
);

interface MarketValueBadgeProps {
  itemId: number;
  currentBid?: number;
  // Pass these from parent to avoid extra query
  marketValueLow?: number;
  marketValueHigh?: number;
  marketValueAvg?: number;
  marketValueConfidence?: string;
}

type Tab = 'estimate' | 'history';

export function MarketValueBadge({
  itemId,
  currentBid,
  marketValueLow,
  marketValueHigh,
  marketValueAvg,
  marketValueConfidence,
}: MarketValueBadgeProps) {
  const [showDetails, setShowDetails] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('estimate');
  const [mounted, setMounted] = useState(false);

  // For portal - need to wait for client-side mount
  useEffect(() => {
    setMounted(true);
  }, []);

  // Listen for global close event (when another modal opens)
  useEffect(() => {
    const handleCloseAll = () => setShowDetails(false);
    window.addEventListener(CLOSE_ALL_ESTIMATE_MODALS, handleCloseAll);
    return () => window.removeEventListener(CLOSE_ALL_ESTIMATE_MODALS, handleCloseAll);
  }, []);

  const openModal = () => {
    // Close any other open modals first
    window.dispatchEvent(new Event(CLOSE_ALL_ESTIMATE_MODALS));
    // Then open this one
    setTimeout(() => setShowDetails(true), 0);
  };

  // Only query if we don't have data from parent
  const needsQuery = !marketValueAvg;

  const { data } = useQuery<{ marketValueEstimate: MarketValueEstimate }>(GET_MARKET_VALUE_ESTIMATE, {
    variables: { itemId },
    skip: !needsQuery, // Skip query if we already have data
    fetchPolicy: 'cache-first',
  });

  // Use parent data if available, otherwise use query data
  const estimate: MarketValueEstimate = needsQuery && data?.marketValueEstimate
    ? data.marketValueEstimate
    : {
        estimatedLow: marketValueLow,
        estimatedHigh: marketValueHigh,
        estimatedAverage: marketValueAvg,
        confidence: marketValueConfidence || 'low',
        notes: '',
      };

  // No data available
  if (!estimate.estimatedAverage) {
    return null;
  }
  const avg = estimate.estimatedAverage || 0;

  // Calculate current bid as percentage of estimated value
  // e.g., bid $5000, estimate $10000 = 50% (good deal - buying at 50% of value)
  const valuePercent = currentBid && avg
    ? (currentBid / avg * 100)
    : null;

  // Determine if it's a good deal based on how much below estimate
  // Under 80% of estimate = good deal, 80-100% = fair, over 100% = overpriced
  const isGoodDeal = valuePercent !== null && valuePercent < 80;
  const isFairDeal = valuePercent !== null && valuePercent >= 80 && valuePercent <= 100;
  const isOverpriced = valuePercent !== null && valuePercent > 100;

  const getBadgeColor = () => {
    if (isGoodDeal) return 'bg-success/15 text-success border-success/30';
    if (isFairDeal) return 'bg-warning/15 text-warning border-warning/30';
    if (isOverpriced) return 'bg-danger/15 text-danger border-danger/30';
    return 'bg-accent/15 text-accent border-accent/30';
  };

  const getConfidenceBadge = () => {
    const colors = {
      high: 'bg-success',
      medium: 'bg-warning',
      low: 'bg-muted',
    };
    return colors[estimate.confidence as keyof typeof colors] || colors.low;
  };

  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (showDetails) {
            setShowDetails(false);
          } else {
            openModal();
          }
        }}
        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors ${getBadgeColor()}`}
      >
        <span className={`w-1.5 h-1.5 rounded-full ${getConfidenceBadge()}`} />
        <span>Est: ${avg.toLocaleString()}</span>
        {valuePercent !== null && (
          <span className="font-bold">
            ({valuePercent.toFixed(0)}%)
          </span>
        )}
      </button>

      {showDetails && mounted && createPortal(
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/60 z-[9998]"
            onClick={(e) => {
              e.stopPropagation();
              setShowDetails(false);
            }}
          />

          {/* Modal */}
          <div className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 z-[9999] bg-panel border border-border rounded-lg shadow-2xl w-[28rem] max-w-[90vw]">
            <div className="p-4">
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-lg font-semibold text-text">Market Value & History</h3>
                <button
                  onClick={() => setShowDetails(false)}
                  className="text-muted hover:text-text transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Tabs */}
              <div className="flex border-b border-border mb-4">
                <button
                  onClick={() => setActiveTab('estimate')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'estimate'
                      ? 'text-accent border-b-2 border-accent'
                      : 'text-text-2 hover:text-text'
                  }`}
                >
                  Estimate
                </button>
                <button
                  onClick={() => setActiveTab('history')}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    activeTab === 'history'
                      ? 'text-accent border-b-2 border-accent'
                      : 'text-text-2 hover:text-text'
                  }`}
                >
                  Price History
                </button>
              </div>

              {/* Tab Content */}
              {activeTab === 'estimate' ? (
                <div className="space-y-3">
                  {/* Current Bid vs Estimate */}
                  {valuePercent !== null && currentBid && (
                    <div className={`flex justify-between items-center py-2 px-2 rounded ${getBadgeColor()}`}>
                      <span className="text-sm font-medium">Current Bid:</span>
                      <span className="text-lg font-bold">
                        ${currentBid.toLocaleString()} ({valuePercent.toFixed(0)}% of est.)
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between items-center py-2 border-b border-border">
                    <span className="text-sm text-text-2">Low Estimate:</span>
                    <span className="text-lg font-bold text-text">${(estimate.estimatedLow || 0).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-border">
                    <span className="text-sm text-text-2">High Estimate:</span>
                    <span className="text-lg font-bold text-text">${(estimate.estimatedHigh || 0).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-2 border-b border-border bg-accent/10 px-2 rounded">
                    <span className="text-sm font-medium text-text">Average Value:</span>
                    <span className="text-xl font-bold text-accent">${avg.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between items-center py-2">
                    <span className="text-sm text-text-2">Confidence:</span>
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      estimate.confidence === 'high' ? 'bg-success/15 text-success' :
                      estimate.confidence === 'medium' ? 'bg-warning/15 text-warning' :
                      'bg-muted/15 text-muted'
                    }`}>
                      {estimate.confidence.toUpperCase()}
                    </span>
                  </div>
                  {estimate.notes && (
                    <div className="pt-3 border-t border-border">
                      <p className="text-xs text-text-2 leading-relaxed">{estimate.notes}</p>
                    </div>
                  )}
                </div>
              ) : (
                <PriceHistoryChart itemId={itemId} days={14} />
              )}

              <button
                onClick={() => setShowDetails(false)}
                className="mt-4 w-full bg-panel-2 hover:bg-hover text-text font-medium py-2 px-4 rounded-md transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </>,
        document.body
      )}
    </>
  );
}
