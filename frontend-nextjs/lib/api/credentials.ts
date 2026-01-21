import { authAPI } from './auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface CredentialStatus {
  auction_house: string;
  has_credentials: boolean;
  is_valid: boolean | null;
  has_active_session: boolean;
}

export interface CredentialResponse {
  auction_house: string;
  username_hint: string;
  is_valid: boolean;
  last_verified: string | null;
  last_error: string | null;
}

export interface LoginResponse {
  success: boolean;
  message: string;
}

// Auction house display info
export const AUCTION_HOUSES = [
  { id: 'goldin', name: 'Goldin', logo: '/logos/goldin.png', color: '#D4AF37' },
  { id: 'fanatics', name: 'Fanatics Collect', logo: '/logos/fanatics.png', color: '#E31837' },
  { id: 'heritage', name: 'Heritage Auctions', logo: '/logos/heritage.png', color: '#003366' },
  { id: 'pristine', name: 'Pristine Auction', logo: '/logos/pristine.png', color: '#1E90FF' },
  { id: 'rea', name: 'REA (Robert Edward)', logo: '/logos/rea.png', color: '#8B4513' },
] as const;

class CredentialsAPI {
  private getHeaders(): HeadersInit {
    const token = authAPI.getAccessToken();
    return {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  async getStatus(): Promise<CredentialStatus[]> {
    const response = await fetch(`${API_URL}/credentials/status`, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      throw new Error('Failed to get credential status');
    }

    return response.json();
  }

  async getCredentials(): Promise<CredentialResponse[]> {
    const response = await fetch(`${API_URL}/credentials`, {
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 401) throw new Error('Not authenticated');
      throw new Error('Failed to get credentials');
    }

    return response.json();
  }

  async storeCredential(
    auctionHouse: string,
    username: string,
    password: string
  ): Promise<CredentialResponse> {
    const response = await fetch(`${API_URL}/credentials`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({
        auction_house: auctionHouse,
        username,
        password,
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to store credential');
    }

    return response.json();
  }

  async deleteCredential(auctionHouse: string): Promise<void> {
    const response = await fetch(`${API_URL}/credentials/${auctionHouse}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      if (response.status === 404) throw new Error('Credential not found');
      throw new Error('Failed to delete credential');
    }
  }

  async testLogin(auctionHouse: string): Promise<LoginResponse> {
    const response = await fetch(`${API_URL}/credentials/${auctionHouse}/login`, {
      method: 'POST',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login test failed');
    }

    return response.json();
  }

  async logout(auctionHouse: string): Promise<void> {
    const response = await fetch(`${API_URL}/credentials/${auctionHouse}/logout`, {
      method: 'POST',
      headers: this.getHeaders(),
    });

    if (!response.ok) {
      throw new Error('Logout failed');
    }
  }
}

export const credentialsAPI = new CredentialsAPI();
