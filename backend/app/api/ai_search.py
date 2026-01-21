"""
AI Search API Endpoint
Provides natural language search capabilities for auction items
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.ai_search import AISearchService

router = APIRouter(prefix="/ai", tags=["AI Search"])


class AISearchRequest(BaseModel):
    query: str


class SearchFilters(BaseModel):
    auction_house: Optional[str] = None
    item_type: Optional[str] = None
    sport: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    grading_company: Optional[str] = None
    min_grade: Optional[str] = None
    sort_by: Optional[str] = None
    ending_soon: Optional[bool] = None


class AISearchResponse(BaseModel):
    search_terms: str
    filters: SearchFilters
    explanation: str
    player_name: Optional[str] = None
    year: Optional[str] = None
    is_rookie: Optional[bool] = None
    suggestions: Optional[List[str]] = None


@router.post("/search", response_model=AISearchResponse)
async def ai_search(request: AISearchRequest):
    """
    Interpret a natural language search query and return structured search criteria.

    Examples:
    - "rookie year Justin Jefferson cards"
    - "PSA 10 Michael Jordan under $500"
    - "best deals on basketball memorabilia"
    - "what's ending soon on Goldin"
    """
    if not request.query or len(request.query.strip()) < 2:
        raise HTTPException(status_code=400, detail="Query must be at least 2 characters")

    try:
        service = AISearchService()
        result = service.interpret_query(request.query)

        # Map the result to our response model
        raw_filters = result.get('filters', {})
        min_grade_val = raw_filters.get('min_grade')
        filters = SearchFilters(
            auction_house=raw_filters.get('auction_house'),
            item_type=raw_filters.get('item_type'),
            sport=raw_filters.get('sport'),
            min_price=raw_filters.get('min_price'),
            max_price=raw_filters.get('max_price'),
            grading_company=raw_filters.get('grading_company'),
            min_grade=str(min_grade_val) if min_grade_val is not None else None,
            sort_by=raw_filters.get('sort_by'),
            ending_soon=raw_filters.get('ending_soon'),
        )

        return AISearchResponse(
            search_terms=result.get('search_terms', request.query),
            filters=filters,
            explanation=result.get('explanation', f"Searching for: {request.query}"),
            player_name=result.get('player_name'),
            year=str(result.get('year')) if result.get('year') else None,
            is_rookie=result.get('is_rookie'),
            suggestions=result.get('suggestions'),
        )

    except ValueError as e:
        # API key not configured
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions():
    """
    Get example search queries to help users understand AI search capabilities.
    """
    return {
        "suggestions": [
            {
                "query": "rookie year Justin Jefferson cards",
                "description": "Find rookie cards from a specific player's debut year"
            },
            {
                "query": "PSA 10 basketball cards under $200",
                "description": "High-grade cards within a budget"
            },
            {
                "query": "best deals on baseball memorabilia",
                "description": "Find undervalued items"
            },
            {
                "query": "what's ending today on Goldin",
                "description": "Time-sensitive auctions on a specific house"
            },
            {
                "query": "vintage Michael Jordan cards",
                "description": "Classic cards from a legendary player"
            },
            {
                "query": "autographed football jerseys",
                "description": "Signed memorabilia from a specific sport"
            },
        ]
    }
