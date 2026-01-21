'use client';

import { useState } from 'react';
import { CredentialStatus, credentialsAPI, AUCTION_HOUSES } from '@/lib/api/credentials';

interface ConnectionCardProps {
  auctionHouse: (typeof AUCTION_HOUSES)[number];
  status: CredentialStatus | undefined;
  onUpdate: () => void;
}

export function ConnectionCard({ auctionHouse, status, onUpdate }: ConnectionCardProps) {
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [testingLogin, setTestingLogin] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const hasCredentials = status?.has_credentials ?? false;
  const isValid = status?.is_valid ?? null;
  const hasActiveSession = status?.has_active_session ?? false;

  const handleSaveCredentials = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      await credentialsAPI.storeCredential(auctionHouse.id, username, password);
      setSuccessMessage('Credentials saved successfully');
      setShowForm(false);
      setUsername('');
      setPassword('');
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save credentials');
    } finally {
      setLoading(false);
    }
  };

  const handleTestLogin = async () => {
    setError(null);
    setSuccessMessage(null);
    setTestingLogin(true);

    try {
      const result = await credentialsAPI.testLogin(auctionHouse.id);
      if (result.success) {
        setSuccessMessage(result.message || 'Login successful');
      } else {
        setError(result.message || 'Login failed');
      }
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login test failed');
    } finally {
      setTestingLogin(false);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm(`Remove ${auctionHouse.name} credentials?`)) return;

    setError(null);
    setSuccessMessage(null);
    setLoading(true);

    try {
      await credentialsAPI.deleteCredential(auctionHouse.id);
      setSuccessMessage('Credentials removed');
      onUpdate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to remove credentials');
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = () => {
    if (!hasCredentials) {
      return <span className="px-2 py-1 text-xs rounded-full bg-gray-500/20 text-gray-400">Not Connected</span>;
    }
    if (hasActiveSession) {
      return <span className="px-2 py-1 text-xs rounded-full bg-green-500/20 text-green-400">Active Session</span>;
    }
    if (isValid === true) {
      return <span className="px-2 py-1 text-xs rounded-full bg-blue-500/20 text-blue-400">Connected</span>;
    }
    if (isValid === false) {
      return <span className="px-2 py-1 text-xs rounded-full bg-red-500/20 text-red-400">Invalid</span>;
    }
    return <span className="px-2 py-1 text-xs rounded-full bg-yellow-500/20 text-yellow-400">Pending</span>;
  };

  return (
    <div className="bg-panel border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-white font-bold text-sm"
            style={{ backgroundColor: auctionHouse.color }}
          >
            {auctionHouse.name.charAt(0)}
          </div>
          <div>
            <h3 className="font-medium text-text">{auctionHouse.name}</h3>
            {getStatusBadge()}
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-3 text-red-500 text-sm bg-red-500/10 border border-red-500/20 rounded-md p-2">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="mb-3 text-green-500 text-sm bg-green-500/10 border border-green-500/20 rounded-md p-2">
          {successMessage}
        </div>
      )}

      {showForm ? (
        <form onSubmit={handleSaveCredentials} className="space-y-3">
          <div>
            <label className="block text-sm text-text-2 mb-1">
              {auctionHouse.id === 'goldin' ? 'Email' : 'Username'}
            </label>
            <input
              type={auctionHouse.id === 'goldin' ? 'email' : 'text'}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-3 py-2 bg-bg border border-border rounded-md text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder={`Your ${auctionHouse.name} ${auctionHouse.id === 'goldin' ? 'email' : 'username'}`}
            />
          </div>
          <div>
            <label className="block text-sm text-text-2 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 bg-bg border border-border rounded-md text-text text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              placeholder="Your password"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2 px-3 bg-accent hover:bg-accent/80 disabled:bg-accent/50 text-white text-sm font-medium rounded-md transition-colors"
            >
              {loading ? 'Saving...' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                setShowForm(false);
                setError(null);
              }}
              className="py-2 px-3 border border-border text-text-2 hover:text-text text-sm rounded-md transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex gap-2">
          {hasCredentials ? (
            <>
              <button
                onClick={handleTestLogin}
                disabled={testingLogin}
                className="flex-1 py-2 px-3 bg-accent hover:bg-accent/80 disabled:bg-accent/50 text-white text-sm font-medium rounded-md transition-colors"
              >
                {testingLogin ? 'Testing...' : 'Test Login'}
              </button>
              <button
                onClick={() => setShowForm(true)}
                className="py-2 px-3 border border-border text-text-2 hover:text-text text-sm rounded-md transition-colors"
              >
                Update
              </button>
              <button
                onClick={handleDisconnect}
                disabled={loading}
                className="py-2 px-3 border border-red-500/50 text-red-400 hover:bg-red-500/10 text-sm rounded-md transition-colors"
              >
                Remove
              </button>
            </>
          ) : (
            <button
              onClick={() => setShowForm(true)}
              className="w-full py-2 px-3 border border-border text-text-2 hover:text-text hover:border-accent text-sm rounded-md transition-colors"
            >
              Connect Account
            </button>
          )}
        </div>
      )}
    </div>
  );
}
