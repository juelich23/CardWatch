"""
GraphQL Types using Strawberry
Converts SQLAlchemy models to GraphQL types
"""
import strawberry
from typing import Optional, List
from datetime import datetime


@strawberry.type
class AuctionType:
    """GraphQL type for Auction"""
    id: int
    auction_house: str
    external_id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str
    created_at: datetime
    updated_at: datetime


@strawberry.type
class AuctionItemType:
    """GraphQL type for AuctionItem"""
    id: int
    auction_id: int
    auction_house: str
    external_id: str
    lot_number: Optional[str] = None
    cert_number: Optional[str] = None

    # Grading
    sub_category: Optional[str] = None
    grading_company: Optional[str] = None
    grade: Optional[str] = None

    # Details
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    sport: Optional[str] = None

    # Images
    image_url: Optional[str] = None

    # Pricing
    current_bid: Optional[float] = None
    starting_bid: Optional[float] = None
    reserve_price: Optional[float] = None
    buy_now_price: Optional[float] = None
    bid_count: int = 0

    # Alt pricing
    alt_price_estimate: Optional[float] = None

    # Market value estimate (cached from LLM)
    market_value_low: Optional[float] = None
    market_value_high: Optional[float] = None
    market_value_avg: Optional[float] = None
    market_value_confidence: Optional[str] = None

    # Timing
    end_time: Optional[datetime] = None

    # Status
    status: str
    is_watched: bool = False

    # URL
    item_url: Optional[str] = None

    # Metadata
    created_at: datetime
    updated_at: datetime


@strawberry.type
class PaginatedAuctionItems:
    """Paginated list of auction items"""
    items: List[AuctionItemType]
    total: int
    page: int
    page_size: int
    has_more: bool


@strawberry.type
class MarketValueEstimate:
    """Market value estimate from Claude API"""
    estimated_low: Optional[float] = None
    estimated_high: Optional[float] = None
    estimated_average: Optional[float] = None
    confidence: str = "low"
    notes: str = ""


@strawberry.type
class GenericResponse:
    """Generic response for mutations"""
    success: bool
    message: str


@strawberry.type
class PriceSnapshotType:
    """Historical price snapshot for an auction item"""
    snapshot_date: datetime
    current_bid: Optional[float]
    bid_count: int
    status: str


def auction_item_from_model(item, is_watched: bool = None) -> AuctionItemType:
    """Convert SQLAlchemy AuctionItem model to GraphQL type

    Args:
        item: SQLAlchemy AuctionItem model
        is_watched: Optional override for is_watched (for per-user watchlist).
                    If None, falls back to item.is_watched (deprecated global flag).
    """
    return AuctionItemType(
        id=item.id,
        auction_id=item.auction_id,
        auction_house=item.auction_house,
        external_id=item.external_id,
        lot_number=item.lot_number,
        cert_number=item.cert_number,
        sub_category=item.sub_category,
        grading_company=item.grading_company,
        grade=item.grade,
        title=item.title,
        description=item.description,
        category=item.category,
        sport=item.sport,
        image_url=item.image_url,
        current_bid=item.current_bid,
        starting_bid=item.starting_bid,
        reserve_price=item.reserve_price,
        buy_now_price=item.buy_now_price,
        bid_count=item.bid_count,
        alt_price_estimate=item.alt_price_estimate,
        market_value_low=item.market_value_low,
        market_value_high=item.market_value_high,
        market_value_avg=item.market_value_avg,
        market_value_confidence=item.market_value_confidence,
        end_time=item.end_time,
        status=item.status,
        is_watched=is_watched if is_watched is not None else item.is_watched,
        item_url=item.item_url,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def auction_from_model(auction) -> AuctionType:
    """Convert SQLAlchemy Auction model to GraphQL type"""
    return AuctionType(
        id=auction.id,
        auction_house=auction.auction_house,
        external_id=auction.external_id,
        title=auction.title,
        description=auction.description,
        category=auction.category,
        start_time=auction.start_time,
        end_time=auction.end_time,
        status=auction.status,
        created_at=auction.created_at,
        updated_at=auction.updated_at,
    )
