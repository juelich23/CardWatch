/**
 * AI Search API Client
 * Handles natural language search queries
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'https://cardwatch-api-production.up.railway.app';

export interface SearchFilters {
  auction_house?: string | null;
  item_type?: string | null;
  sport?: string | null;
  min_price?: number | null;
  max_price?: number | null;
  grading_company?: string | null;
  min_grade?: string | null;
  sort_by?: string | null;
  ending_soon?: boolean | null;
}

export interface AISearchResponse {
  search_terms: string;
  filters: SearchFilters;
  explanation: string;
  player_name?: string | null;
  year?: string | null;
  is_rookie?: boolean | null;
  suggestions?: string[] | null;
}

export interface SearchSuggestion {
  query: string;
  description: string;
}

export const aiSearchAPI = {
  /**
   * Interpret a natural language search query
   */
  async search(query: string): Promise<AISearchResponse> {
    const response = await fetch(`${API_URL}/ai/search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'AI search failed' }));
      throw new Error(error.detail || 'AI search failed');
    }

    return response.json();
  },

  /**
   * Get example search suggestions
   */
  async getSuggestions(): Promise<{ suggestions: SearchSuggestion[] }> {
    const response = await fetch(`${API_URL}/ai/suggestions`);

    if (!response.ok) {
      throw new Error('Failed to get suggestions');
    }

    return response.json();
  },
};
