#!/usr/bin/env python3
"""
Market Value Estimation Service
Uses Claude API to estimate card values based on title and market data
"""

import os
import json
import anthropic
import redis
from typing import Optional
from datetime import datetime, timedelta
from app.config import get_settings


class MarketValueEstimator:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)

        # Try to connect to Redis, fall back to in-memory cache if not available
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            self.use_redis = True
            print("✅ Connected to Redis for market value caching")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"⚠️  Redis not available, using in-memory cache: {e}")
            self.redis_client = None
            self.use_redis = False
            self.cache = {}  # Fallback in-memory cache

        self.cache_ttl = timedelta(hours=24)  # Cache for 24 hours
        self.cache_ttl_seconds = int(self.cache_ttl.total_seconds())

    def _get_cache_key(self, title: str, grading_company: Optional[str], grade: Optional[str]) -> str:
        """Generate cache key for a card"""
        key = f"market_value:{title}|{grading_company or 'NONE'}|{grade or 'NONE'}"
        return key

    def _get_cached_value(self, cache_key: str) -> Optional[dict]:
        """Get value from cache (Redis or in-memory)"""
        if self.use_redis and self.redis_client:
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception as e:
                print(f"Redis cache get error: {e}")
        else:
            # In-memory fallback
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if datetime.now() - entry['timestamp'] < self.cache_ttl:
                    return entry['data']
        return None

    def _set_cached_value(self, cache_key: str, value: dict):
        """Set value in cache (Redis or in-memory)"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.setex(
                    cache_key,
                    self.cache_ttl_seconds,
                    json.dumps(value)
                )
            except Exception as e:
                print(f"Redis cache set error: {e}")
        else:
            # In-memory fallback
            self.cache[cache_key] = {
                'data': value,
                'timestamp': datetime.now()
            }

    def estimate_value(
        self,
        title: str,
        grading_company: Optional[str] = None,
        grade: Optional[str] = None,
        current_bid: Optional[float] = None
    ) -> dict:
        """
        Estimate market value for a card using Claude API

        Returns:
            dict with keys:
                - estimated_low: Low end of value range
                - estimated_high: High end of value range
                - estimated_average: Average estimated value
                - confidence: Confidence level (low/medium/high)
                - notes: Additional notes about the estimate
        """

        # Check cache first
        cache_key = self._get_cache_key(title, grading_company, grade)
        cached_value = self._get_cached_value(cache_key)
        if cached_value:
            return cached_value

        # Build the prompt
        grading_info = ""
        if grading_company and grade:
            grading_info = f", graded {grading_company} {grade}"
        elif grading_company:
            grading_info = f", graded by {grading_company}"

        current_bid_info = ""
        if current_bid:
            current_bid_info = f"\nCurrent auction bid: ${current_bid:,.2f}"

        prompt = f"""You are a sports card and collectibles market expert. Based on the following card details, provide a realistic market value estimate.

Card: {title}{grading_info}{current_bid_info}

Please analyze this card and provide:
1. A realistic value range (low to high)
2. Your best estimate for current market value
3. Confidence level (low/medium/high)
4. Brief notes about factors affecting value

Consider:
- Player popularity and significance
- Card rarity and year
- Grading company and grade (if applicable)
- Current market trends
- Recent sales data if you have knowledge of it

Respond ONLY with valid JSON in this exact format:
{{
    "estimated_low": <number>,
    "estimated_high": <number>,
    "estimated_average": <number>,
    "confidence": "<low|medium|high>",
    "notes": "<brief explanation>"
}}"""

        try:
            # Call Claude API
            # Using Haiku for cost-effectiveness
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract JSON from response (in case there's extra text)
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                response_text = response_text[json_start:json_end]

            result = json.loads(response_text)

            # Validate response structure
            required_keys = ['estimated_low', 'estimated_high', 'estimated_average', 'confidence', 'notes']
            for key in required_keys:
                if key not in result:
                    raise ValueError(f"Missing required key: {key}")

            # Cache the result
            self._set_cached_value(cache_key, result)

            return result

        except Exception as e:
            print(f"Error estimating value for '{title}': {e}")
            # Return a fallback response
            return {
                "estimated_low": None,
                "estimated_high": None,
                "estimated_average": None,
                "confidence": "low",
                "notes": f"Unable to estimate value: {str(e)}"
            }

    def batch_estimate_values(
        self,
        items: list[dict],
        max_items: int = 10
    ) -> dict[int, dict]:
        """
        Estimate values for multiple items

        Args:
            items: List of dicts with keys: id, title, grading_company, grade, current_bid
            max_items: Maximum number of items to process

        Returns:
            Dict mapping item_id to estimation result
        """
        results = {}

        for i, item in enumerate(items[:max_items]):
            item_id = item.get('id')
            title = item.get('title')

            if not title:
                continue

            print(f"Estimating value {i+1}/{min(len(items), max_items)}: {title[:50]}...")

            estimate = self.estimate_value(
                title=title,
                grading_company=item.get('grading_company'),
                grade=item.get('grade'),
                current_bid=item.get('current_bid')
            )

            if item_id:
                results[item_id] = estimate

        return results


# Example usage
if __name__ == "__main__":
    estimator = MarketValueEstimator()

    # Test with a sample card
    result = estimator.estimate_value(
        title="2000 Bowman Chrome Tom Brady Rookie #236 PSA 10 GEM MINT",
        grading_company="PSA",
        grade="10",
        current_bid=3900.00
    )

    print(json.dumps(result, indent=2))
