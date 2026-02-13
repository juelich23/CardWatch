import { authAPI } from './auth';
import type {
  BiddingRule,
  BiddingRuleCreate,
  GixenSnipe,
  SnipeStats,
  GixenCredentialStatus,
  RuleTestResult,
} from '@/lib/types/bidding';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class BiddingAPI {
  private getHeaders(): HeadersInit {
    const token = authAPI.getAccessToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      if (response.status === 401) throw new Error('Please sign in');
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Request failed (${response.status})`);
    }
    return response.json();
  }

  // ─── Gixen Credentials ─────────────────────────────────────────────────

  async storeGixenCredentials(username: string, password: string): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/gixen-credentials`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ username, password }),
    });
    return this.handleResponse(response);
  }

  async getGixenCredentialStatus(): Promise<GixenCredentialStatus> {
    const response = await fetch(`${API_URL}/api/bidding/gixen-credentials/status`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async deleteGixenCredentials(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/gixen-credentials`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async verifyGixenCredentials(): Promise<{ valid: boolean; message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/gixen-credentials/verify`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  // ─── Rules ─────────────────────────────────────────────────────────────

  async listRules(): Promise<BiddingRule[]> {
    const response = await fetch(`${API_URL}/api/bidding/rules`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async createRule(rule: BiddingRuleCreate): Promise<BiddingRule> {
    const response = await fetch(`${API_URL}/api/bidding/rules`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(rule),
    });
    return this.handleResponse(response);
  }

  async updateRule(id: number, updates: Partial<BiddingRuleCreate>): Promise<BiddingRule> {
    const response = await fetch(`${API_URL}/api/bidding/rules/${id}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(updates),
    });
    return this.handleResponse(response);
  }

  async deleteRule(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/rules/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async toggleRule(id: number): Promise<{ is_active: boolean }> {
    const response = await fetch(`${API_URL}/api/bidding/rules/${id}/toggle`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async testRule(id: number): Promise<RuleTestResult> {
    const response = await fetch(`${API_URL}/api/bidding/rules/${id}/test`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  // ─── Snipes ────────────────────────────────────────────────────────────

  async listSnipes(params?: {
    status?: string;
    rule_id?: number;
    limit?: number;
    offset?: number;
  }): Promise<GixenSnipe[]> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status_filter', params.status);
    if (params?.rule_id) searchParams.set('rule_id', String(params.rule_id));
    if (params?.limit) searchParams.set('limit', String(params.limit));
    if (params?.offset) searchParams.set('offset', String(params.offset));

    const qs = searchParams.toString();
    const response = await fetch(`${API_URL}/api/bidding/snipes${qs ? `?${qs}` : ''}`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async createSnipe(itemId: number, maxBid: number, bidOffsetSeconds: number = 6): Promise<GixenSnipe> {
    const response = await fetch(`${API_URL}/api/bidding/snipes`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        item_id: itemId,
        max_bid: maxBid,
        bid_offset_seconds: bidOffsetSeconds,
      }),
    });
    return this.handleResponse(response);
  }

  async cancelSnipe(id: number): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/snipes/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async getSnipeStats(): Promise<SnipeStats> {
    const response = await fetch(`${API_URL}/api/bidding/snipes/stats`, {
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  // ─── Actions ───────────────────────────────────────────────────────────

  async runRules(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/run-rules`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async syncGixen(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/sync-gixen`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }

  async submitPending(): Promise<{ message: string }> {
    const response = await fetch(`${API_URL}/api/bidding/submit-pending`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    return this.handleResponse(response);
  }
}

export const biddingAPI = new BiddingAPI();
