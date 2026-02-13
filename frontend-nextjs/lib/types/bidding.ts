export interface BiddingRule {
  id: number;
  name: string;
  is_active: boolean;
  title_contains: string | null;
  title_excludes: string | null;
  sport: string | null;
  grading_company: string | null;
  min_grade: number | null;
  max_grade: number | null;
  item_type: string | null;
  category: string | null;
  max_bid: number;
  bid_strategy: 'fixed' | 'current_plus_pct' | 'market_value_pct';
  bid_pct: number | null;
  max_active_snipes: number;
  max_current_bid: number | null;
  min_end_hours: number;
  max_end_hours: number | null;
  bid_offset_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface BiddingRuleCreate {
  name: string;
  title_contains?: string;
  title_excludes?: string;
  sport?: string;
  grading_company?: string;
  min_grade?: number;
  max_grade?: number;
  item_type?: string;
  category?: string;
  max_bid: number;
  bid_strategy?: string;
  bid_pct?: number;
  max_active_snipes?: number;
  max_current_bid?: number;
  min_end_hours?: number;
  max_end_hours?: number;
  bid_offset_seconds?: number;
}

export interface GixenSnipe {
  id: number;
  user_id: number;
  rule_id: number | null;
  item_id: number;
  ebay_item_id: string;
  max_bid: number;
  bid_offset_seconds: number;
  current_bid_at_snipe: number | null;
  status: string;
  gixen_status: string | null;
  gixen_message: string | null;
  final_price: number | null;
  won: boolean | null;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  item_title: string | null;
  item_image_url: string | null;
  item_end_time: string | null;
  rule_name: string | null;
}

export interface SnipeStats {
  total: number;
  pending: number;
  submitted: number;
  active: number;
  won: number;
  lost: number;
  error: number;
  expired: number;
  cancelled: number;
  win_rate: number | null;
  total_spent: number;
}

export interface GixenCredentialStatus {
  has_credentials: boolean;
  is_valid: boolean | null;
  last_verified: string | null;
  last_error: string | null;
}

export interface RuleTestResult {
  matches: Array<{
    item_id: number;
    external_id: string;
    title: string;
    current_bid: number | null;
    end_time: string | null;
    image_url: string | null;
    calculated_bid: number;
  }>;
  count: number;
}
