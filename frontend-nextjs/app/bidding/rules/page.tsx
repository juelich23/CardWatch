'use client';

import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { biddingAPI } from '@/lib/api/bidding';
import type { BiddingRule, BiddingRuleCreate, RuleTestResult } from '@/lib/types/bidding';

const DEFAULT_RULE: BiddingRuleCreate = {
  name: '',
  max_bid: 0,
  bid_strategy: 'fixed',
  max_active_snipes: 10,
  min_end_hours: 1.0,
  bid_offset_seconds: 6,
};

export default function RulesPage() {
  const [rules, setRules] = useState<BiddingRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<BiddingRule | null>(null);
  const [formData, setFormData] = useState<BiddingRuleCreate>(DEFAULT_RULE);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState<RuleTestResult | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  const loadRules = useCallback(async () => {
    try {
      const data = await biddingAPI.listRules();
      setRules(data);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load rules');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const openCreate = () => {
    setEditingRule(null);
    setFormData(DEFAULT_RULE);
    setDialogOpen(true);
  };

  const openEdit = (rule: BiddingRule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      title_contains: rule.title_contains || undefined,
      title_excludes: rule.title_excludes || undefined,
      sport: rule.sport || undefined,
      grading_company: rule.grading_company || undefined,
      min_grade: rule.min_grade || undefined,
      max_grade: rule.max_grade || undefined,
      item_type: rule.item_type || undefined,
      category: rule.category || undefined,
      max_bid: rule.max_bid,
      bid_strategy: rule.bid_strategy,
      bid_pct: rule.bid_pct || undefined,
      max_active_snipes: rule.max_active_snipes,
      max_current_bid: rule.max_current_bid || undefined,
      min_end_hours: rule.min_end_hours,
      max_end_hours: rule.max_end_hours || undefined,
      bid_offset_seconds: rule.bid_offset_seconds,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editingRule) {
        await biddingAPI.updateRule(editingRule.id, formData);
      } else {
        await biddingAPI.createRule(formData);
      }
      setDialogOpen(false);
      loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save rule');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this rule? Associated pending snipes will also be removed.')) return;
    try {
      await biddingAPI.deleteRule(id);
      loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const handleToggle = async (id: number) => {
    try {
      await biddingAPI.toggleRule(id);
      loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to toggle');
    }
  };

  const handleTest = async (id: number) => {
    setTestingId(id);
    setTestResult(null);
    try {
      const result = await biddingAPI.testRule(id);
      setTestResult(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Test failed');
    } finally {
      setTestingId(null);
    }
  };

  const updateForm = (field: string, value: string | number | undefined) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-text mb-6">Bidding Rules</h1>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 bg-panel rounded-lg animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-text">Bidding Rules</h1>
        <Button onClick={openCreate}>Create Rule</Button>
      </div>

      {error && <p className="text-red-400 text-sm mb-4">{error}</p>}

      {rules.length === 0 ? (
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-text-2">No bidding rules yet.</p>
            <Button onClick={openCreate} className="mt-4">Create Your First Rule</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {rules.map((rule) => (
            <Card key={rule.id}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <h3 className="text-lg font-semibold text-text">{rule.name}</h3>
                      <Badge className={rule.is_active ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}>
                        {rule.is_active ? 'Active' : 'Paused'}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-2 text-sm text-text-2">
                      {rule.title_contains && (
                        <span>Contains: &quot;{rule.title_contains}&quot;</span>
                      )}
                      {rule.sport && <Badge variant="outline">{rule.sport}</Badge>}
                      {rule.grading_company && <Badge variant="outline">{rule.grading_company}</Badge>}
                      {rule.min_grade != null && (
                        <span>Grade: {rule.min_grade}{rule.max_grade != null ? `–${rule.max_grade}` : '+'}</span>
                      )}
                      {rule.category && <Badge variant="outline">{rule.category}</Badge>}
                    </div>
                    <div className="flex flex-wrap gap-4 mt-2 text-sm text-text-2">
                      <span>Max bid: <strong className="text-text">${rule.max_bid.toFixed(2)}</strong></span>
                      <span>Strategy: {rule.bid_strategy}</span>
                      <span>Offset: {rule.bid_offset_seconds}s</span>
                      <span>Max snipes: {rule.max_active_snipes}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Switch
                      checked={rule.is_active}
                      onCheckedChange={() => handleToggle(rule.id)}
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleTest(rule.id)}
                      disabled={testingId === rule.id}
                    >
                      {testingId === rule.id ? 'Testing...' : 'Test'}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => openEdit(rule)}>
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => handleDelete(rule.id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Test Results */}
      {testResult && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle className="text-lg">
              Test Results ({testResult.count} matches)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {testResult.matches.length === 0 ? (
              <p className="text-text-2 text-sm">No matching eBay items found.</p>
            ) : (
              <div className="space-y-2">
                {testResult.matches.slice(0, 20).map((match) => (
                  <div key={match.item_id} className="flex items-center gap-3 p-2 rounded bg-panel-2/50">
                    {match.image_url && (
                      <img src={match.image_url} alt="" className="w-10 h-10 rounded object-cover" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text truncate">{match.title}</p>
                      <p className="text-xs text-text-2">
                        Current: ${match.current_bid?.toFixed(2) || '0.00'} |
                        Calculated bid: ${match.calculated_bid.toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
            <Button variant="outline" size="sm" className="mt-3" onClick={() => setTestResult(null)}>
              Dismiss
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingRule ? 'Edit Rule' : 'Create Rule'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-4">
            {/* Rule Name */}
            <div>
              <Label>Rule Name</Label>
              <Input
                value={formData.name}
                onChange={(e) => updateForm('name', e.target.value)}
                placeholder="e.g., PSA 10 Basketball Rookies"
              />
            </div>

            {/* Title Matching */}
            <div className="space-y-3">
              <h4 className="font-medium text-text">Title Matching</h4>
              <div>
                <Label>Title Contains (comma-separated, AND logic)</Label>
                <Input
                  value={formData.title_contains || ''}
                  onChange={(e) => updateForm('title_contains', e.target.value || undefined)}
                  placeholder="e.g., PSA 10, Rookie"
                />
              </div>
              <div>
                <Label>Title Excludes (comma-separated, OR logic)</Label>
                <Input
                  value={formData.title_excludes || ''}
                  onChange={(e) => updateForm('title_excludes', e.target.value || undefined)}
                  placeholder="e.g., reprint, damaged"
                />
              </div>
            </div>

            {/* Card Filters */}
            <div className="space-y-3">
              <h4 className="font-medium text-text">Card Filters</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Sport</Label>
                  <Input
                    value={formData.sport || ''}
                    onChange={(e) => updateForm('sport', e.target.value || undefined)}
                    placeholder="e.g., basketball"
                  />
                </div>
                <div>
                  <Label>Grading Company</Label>
                  <Input
                    value={formData.grading_company || ''}
                    onChange={(e) => updateForm('grading_company', e.target.value || undefined)}
                    placeholder="e.g., PSA"
                  />
                </div>
                <div>
                  <Label>Min Grade</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.min_grade ?? ''}
                    onChange={(e) => updateForm('min_grade', e.target.value ? Number(e.target.value) : undefined)}
                  />
                </div>
                <div>
                  <Label>Max Grade</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.max_grade ?? ''}
                    onChange={(e) => updateForm('max_grade', e.target.value ? Number(e.target.value) : undefined)}
                  />
                </div>
                <div>
                  <Label>Item Type</Label>
                  <Input
                    value={formData.item_type || ''}
                    onChange={(e) => updateForm('item_type', e.target.value || undefined)}
                    placeholder="e.g., CARD"
                  />
                </div>
                <div>
                  <Label>Category</Label>
                  <Input
                    value={formData.category || ''}
                    onChange={(e) => updateForm('category', e.target.value || undefined)}
                    placeholder="e.g., Trading Cards"
                  />
                </div>
              </div>
            </div>

            {/* Bid Config */}
            <div className="space-y-3">
              <h4 className="font-medium text-text">Bid Configuration</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Max Bid ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.max_bid || ''}
                    onChange={(e) => updateForm('max_bid', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Strategy</Label>
                  <Select
                    value={formData.bid_strategy || 'fixed'}
                    onValueChange={(v) => updateForm('bid_strategy', v)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fixed">Fixed (always max bid)</SelectItem>
                      <SelectItem value="current_plus_pct">Current + %</SelectItem>
                      <SelectItem value="market_value_pct">Market Value %</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {formData.bid_strategy !== 'fixed' && (
                  <div>
                    <Label>Bid Percentage (%)</Label>
                    <Input
                      type="number"
                      step="1"
                      value={formData.bid_pct ?? ''}
                      onChange={(e) => updateForm('bid_pct', e.target.value ? Number(e.target.value) : undefined)}
                    />
                  </div>
                )}
                <div>
                  <Label>Snipe Offset (seconds before end)</Label>
                  <Select
                    value={String(formData.bid_offset_seconds || 6)}
                    onValueChange={(v) => updateForm('bid_offset_seconds', Number(v))}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="3">3 seconds</SelectItem>
                      <SelectItem value="6">6 seconds</SelectItem>
                      <SelectItem value="8">8 seconds</SelectItem>
                      <SelectItem value="10">10 seconds</SelectItem>
                      <SelectItem value="15">15 seconds</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Safety Limits */}
            <div className="space-y-3">
              <h4 className="font-medium text-text">Safety Limits</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Max Active Snipes (per rule)</Label>
                  <Input
                    type="number"
                    value={formData.max_active_snipes || 10}
                    onChange={(e) => updateForm('max_active_snipes', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Max Current Bid ($)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={formData.max_current_bid ?? ''}
                    onChange={(e) => updateForm('max_current_bid', e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="No limit"
                  />
                </div>
                <div>
                  <Label>Min Hours Until End</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.min_end_hours || 1.0}
                    onChange={(e) => updateForm('min_end_hours', Number(e.target.value))}
                  />
                </div>
                <div>
                  <Label>Max Hours Until End</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={formData.max_end_hours ?? ''}
                    onChange={(e) => updateForm('max_end_hours', e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="No limit"
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button onClick={handleSave} disabled={saving || !formData.name || !formData.max_bid}>
                {saving ? 'Saving...' : editingRule ? 'Update Rule' : 'Create Rule'}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
