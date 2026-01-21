"""
AI Search Service
Uses Claude API to interpret natural language queries and extract search criteria
"""

import json
import anthropic
from typing import Optional, List
from datetime import datetime
from app.config import get_settings


class AISearchService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def interpret_query(self, query: str, available_items_summary: Optional[str] = None) -> dict:
        """
        Interpret a natural language search query and extract search criteria.

        Args:
            query: The user's natural language query
            available_items_summary: Optional context about what's available

        Returns:
            dict with:
                - search_terms: Keywords to search for in titles
                - filters: Structured filters to apply
                - explanation: Human-readable explanation of interpretation
                - suggestions: Optional follow-up suggestions
        """

        context = """You are a search assistant for a sports card and memorabilia auction aggregator.
Your job is to interpret natural language queries and extract structured search criteria.

The platform aggregates items from auction houses like Goldin, Fanatics, Heritage, Pristine, REA, and others.
Items include trading cards (baseball, basketball, football, etc.), memorabilia, and autographs.

CRITICAL - Rookie Year Knowledge:
When users search for "rookie year" or "rookie cards" of a player, you MUST use your knowledge to determine the player's actual rookie year and include that YEAR in the search terms instead of the word "rookie". Card listings typically include the year (e.g., "2020 Panini Prizm Justin Jefferson") not the word "rookie".

Examples of rookie years you should know:
- Justin Jefferson: 2020 (NFL Draft 2020)
- Ja Morant: 2019 (NBA Draft 2019)
- Luka Doncic: 2018 (NBA Draft 2018)
- Patrick Mahomes: 2017 (NFL Draft 2017)
- Lamar Jackson: 2018 (NFL Draft 2018)
- Joe Burrow: 2020 (NFL Draft 2020)
- Trevor Lawrence: 2021 (NFL Draft 2021)
- Anthony Edwards: 2020 (NBA Draft 2020)
- LaMelo Ball: 2020 (NBA Draft 2020)
- Zion Williamson: 2019 (NBA Draft 2019)
- Jayson Tatum: 2017 (NBA Draft 2017)
- Juan Soto: 2018 (MLB Debut 2018)
- Ronald Acuna Jr: 2018 (MLB Debut 2018)
- Shohei Ohtani: 2018 (MLB Debut USA 2018)
- Victor Wembanyama: 2023 (NBA Draft 2023)
- Connor Bedard: 2023 (NHL Draft 2023)

For older players, use your knowledge of when they were drafted/debuted.

Common query patterns:
- Player searches: "Justin Jefferson rookie cards" → search "2020 justin jefferson"
- Year/rookie searches: "2020 rookies", "rookie year Luka Doncic" → search "2018 luka doncic"
- Grade searches: "PSA 10 cards", "BGS 9.5 or higher"
- Price searches: "cards under $100", "high-value items over $1000"
- Deal searches: "best deals", "undervalued cards"
- Ending soon: "auctions ending today", "about to end"
- Category: "basketball cards", "baseball memorabilia", "autographed items"
- Auction house specific: "Goldin auctions", "what's on Fanatics"

Grading companies: PSA, BGS, SGC, CGC
Sports: Baseball, Basketball, Football, Hockey, Soccer, Golf, Boxing, UFC/MMA
"""

        prompt = f"""{context}

User query: "{query}"

Analyze this query and extract search criteria. Respond with valid JSON only:

{{
    "search_terms": "<optimized keywords to search in item titles - DO NOT include sport name here>",
    "filters": {{
        "auction_house": "<goldin|fanatics|heritage|pristine|rea|null if any>",
        "item_type": "<cards|memorabilia|autographs|null if any>",
        "sport": "<BASKETBALL|BASEBALL|FOOTBALL|HOCKEY|SOCCER|GOLF|BOXING|RACING|OTHER|null if any - MUST be uppercase>",
        "min_price": <number or null>,
        "max_price": <number or null>,
        "grading_company": "<PSA|BGS|SGC|CGC|null if any>",
        "min_grade": "<minimum grade number or null>",
        "sort_by": "<priceHigh|priceLow|endTime|bestValue|bidCount - pick most relevant>",
        "ending_soon": <true if they want items ending soon, false otherwise>
    }},
    "explanation": "<brief, friendly explanation of what you're searching for>",
    "player_name": "<extracted player name if mentioned, null otherwise>",
    "year": "<the actual year - CRITICAL: if user mentions 'rookie' for a player, use their actual rookie year here>",
    "is_rookie": <true if searching for rookie cards specifically, false otherwise>
}}

CRITICAL RULES for search_terms:
1. For rookie searches: Use "[YEAR] [player name]" format (e.g., "2020 justin jefferson" NOT "justin jefferson rookie")
2. Card listings contain the year in the title, not the word "rookie" - so search by year!
3. Example: "rookie year Justin Jefferson cards" → search_terms: "2020 justin jefferson", year: "2020"
4. Example: "Ja Morant rookies" → search_terms: "2019 ja morant", year: "2019"
5. DO NOT include sport names (basketball, football, baseball, etc.) in search_terms - use the sport filter instead!
6. Example: "2020 basketball cards" → search_terms: "2020", filters.sport: "BASKETBALL"
7. Example: "Michael Jordan basketball cards" → search_terms: "michael jordan", filters.sport: "BASKETBALL"
8. DO NOT include price terms in search_terms! Extract them as filters instead:
   - "under $200", "below 200", "less than 200" → filters.max_price: 200, NOT in search_terms
   - "over $100", "above 100", "more than 100" → filters.min_price: 100, NOT in search_terms
   - "between $50 and $200" → filters.min_price: 50, filters.max_price: 200
9. Example: "PSA 10 basketball cards under $200" → search_terms: "psa 10", filters.sport: "BASKETBALL", filters.max_price: 200
10. Example: "Jordan cards over $500" → search_terms: "jordan", filters.min_price: 500
11. DO NOT include generic words like "cards", "items", "auctions" in search_terms unless part of a specific term
12. Be generous with search terms - better to return more results than miss relevant items
13. Always provide a friendly explanation"""

        try:
            message = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text.strip()

            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                response_text = response_text[json_start:json_end]

            result = json.loads(response_text)

            # Ensure required keys exist
            if 'search_terms' not in result:
                result['search_terms'] = query
            if 'filters' not in result:
                result['filters'] = {}
            if 'explanation' not in result:
                result['explanation'] = f"Searching for: {query}"

            return result

        except Exception as e:
            print(f"Error interpreting query '{query}': {e}")
            # Return a basic fallback
            return {
                "search_terms": query,
                "filters": {},
                "explanation": f"Searching for: {query}",
                "error": str(e)
            }

    def build_search_query(self, interpretation: dict) -> str:
        """
        Build an optimized search string from the interpretation.
        Combines year and player name - uses year instead of "rookie" since
        card listings typically have the year in the title, not the word "rookie".
        """
        parts = []

        # Add year if specified (this is key for rookie searches - use year, not "rookie")
        if interpretation.get('year'):
            parts.append(str(interpretation['year']))

        # Add player name
        if interpretation.get('player_name'):
            parts.append(interpretation['player_name'])

        # NOTE: We intentionally do NOT add the word "rookie" here.
        # Card listings use the year (e.g., "2020 Panini Prizm Justin Jefferson")
        # not the word "rookie", so searching by year is more effective.

        # If we built specific parts, use those; otherwise use the general search terms
        if parts:
            return ' '.join(parts)

        return interpretation.get('search_terms', '')


# Example usage
if __name__ == "__main__":
    service = AISearchService()

    test_queries = [
        "rookie year Justin Jefferson cards",
        "PSA 10 Michael Jordan under $500",
        "best deals on basketball memorabilia",
        "what's ending soon on Goldin",
    ]

    for query in test_queries:
        print(f"\nQuery: {query}")
        result = service.interpret_query(query)
        print(json.dumps(result, indent=2))
