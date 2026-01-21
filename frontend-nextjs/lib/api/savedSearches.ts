/**
 * Saved Searches API client
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface SavedSearchFilters {
  search?: string;
  auctionHouse?: string;
  itemType?: string;
  sport?: string;
  minPrice?: number;
  maxPrice?: number;
  sortBy?: string;
  gradingCompany?: string;
  category?: string;
}

export interface SavedSearch {
  id: number;
  name: string;
  filters: SavedSearchFilters;
  email_alerts_enabled: boolean;
  created_at: string;
  updated_at: string;
}

class SavedSearchesAPI {
  private getAccessToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('access_token');
  }

  private getHeaders(): HeadersInit {
    const token = this.getAccessToken();
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    return headers;
  }

  async list(): Promise<SavedSearch[]> {
    const response = await fetch(`${API_URL}/saved-searches`, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Please sign in to view saved searches');
      }
      throw new Error('Failed to fetch saved searches');
    }

    return response.json();
  }

  async create(name: string, filters: SavedSearchFilters): Promise<SavedSearch> {
    const response = await fetch(`${API_URL}/saved-searches`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        name,
        filters,
        email_alerts_enabled: false,
      }),
    });

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Please sign in to save searches');
      }
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to save search');
    }

    return response.json();
  }

  async get(id: number): Promise<SavedSearch> {
    const response = await fetch(`${API_URL}/saved-searches/${id}`, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Saved search not found');
      }
      throw new Error('Failed to fetch saved search');
    }

    return response.json();
  }

  async update(id: number, updates: Partial<{ name: string; filters: SavedSearchFilters; email_alerts_enabled: boolean }>): Promise<SavedSearch> {
    const response = await fetch(`${API_URL}/saved-searches/${id}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      body: JSON.stringify(updates),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Saved search not found');
      }
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || 'Failed to update saved search');
    }

    return response.json();
  }

  async delete(id: number): Promise<void> {
    const response = await fetch(`${API_URL}/saved-searches/${id}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('Saved search not found');
      }
      throw new Error('Failed to delete saved search');
    }
  }
}

export const savedSearchesAPI = new SavedSearchesAPI();
