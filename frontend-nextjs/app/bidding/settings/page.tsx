'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { biddingAPI } from '@/lib/api/bidding';
import type { GixenCredentialStatus } from '@/lib/types/bidding';

export default function BiddingSettingsPage() {
  const [credStatus, setCredStatus] = useState<GixenCredentialStatus | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      const status = await biddingAPI.getGixenCredentialStatus();
      setCredStatus(status);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleSave = async () => {
    if (!username || !password) {
      setError('Username and password are required');
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      await biddingAPI.storeGixenCredentials(username, password);
      setSuccess('Gixen credentials saved');
      setUsername('');
      setPassword('');
      loadStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await biddingAPI.verifyGixenCredentials();
      if (result.valid) {
        setSuccess('Credentials verified successfully');
      } else {
        setError(`Verification failed: ${result.message}`);
      }
      loadStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Verification failed');
    } finally {
      setVerifying(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Delete your Gixen credentials? Active snipes will stop working.')) return;
    setDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      await biddingAPI.deleteGixenCredentials();
      setSuccess('Credentials deleted');
      loadStatus();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-text mb-6">Bidding Settings</h1>
        <div className="h-48 bg-panel rounded-lg animate-pulse" />
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <h1 className="text-3xl font-bold text-text mb-6">Bidding Settings</h1>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 rounded-lg bg-green-500/10 border border-green-500/30">
          <p className="text-green-400 text-sm">{success}</p>
        </div>
      )}

      {/* Current Status */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-lg">Gixen Credentials</CardTitle>
        </CardHeader>
        <CardContent>
          {credStatus?.has_credentials ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <span className="text-text-2">Status:</span>
                {credStatus.is_valid === true && (
                  <Badge className="bg-green-500/20 text-green-400">Valid</Badge>
                )}
                {credStatus.is_valid === false && (
                  <Badge className="bg-red-500/20 text-red-400">Invalid</Badge>
                )}
                {credStatus.is_valid === null && (
                  <Badge className="bg-yellow-500/20 text-yellow-400">Not Verified</Badge>
                )}
              </div>
              {credStatus.last_verified && (
                <p className="text-sm text-text-2">
                  Last verified: {new Date(credStatus.last_verified).toLocaleString()}
                </p>
              )}
              {credStatus.last_error && (
                <p className="text-sm text-red-400">
                  Last error: {credStatus.last_error}
                </p>
              )}
              <div className="flex gap-2 mt-4">
                <Button
                  variant="outline"
                  onClick={handleVerify}
                  disabled={verifying}
                >
                  {verifying ? 'Verifying...' : 'Verify Credentials'}
                </Button>
                <Button
                  variant="outline"
                  className="text-red-400 hover:text-red-300"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {deleting ? 'Deleting...' : 'Delete Credentials'}
                </Button>
              </div>
            </div>
          ) : (
            <p className="text-text-2">No Gixen credentials stored. Enter them below to enable sniping.</p>
          )}
        </CardContent>
      </Card>

      {/* Save Credentials Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">
            {credStatus?.has_credentials ? 'Update Credentials' : 'Add Gixen Credentials'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-sm text-text-2">
              Enter your Gixen account credentials. These are stored encrypted and used
              to submit snipes to the Gixen API.
            </p>
            <div>
              <Label>Gixen Username</Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Your Gixen username"
                autoComplete="off"
              />
            </div>
            <div>
              <Label>Gixen Password</Label>
              <Input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Your Gixen password"
                autoComplete="off"
              />
            </div>
            <Button onClick={handleSave} disabled={saving || !username || !password}>
              {saving ? 'Saving...' : 'Save Credentials'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
