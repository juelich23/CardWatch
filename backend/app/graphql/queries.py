"""
GraphQL Queries
Define all read operations for the API
"""
import strawberry
from typing import List, Optional, Set
from datetime import datetime
from sqlalchemy import select, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.models import AuctionItem as AuctionItemModel, Auction as AuctionModel, UserWatchlistItem
from app.graphql.types import (
    AuctionItemType,
    AuctionType,
    PaginatedAuctionItems,
    MarketValueEstimate,
    PriceSnapshotType,
    auction_item_from_model,
    auction_from_model,
)
from app.services.market_value import MarketValueEstimator
from app.services.price_snapshot_service import PriceSnapshotService


async def get_db_session() -> AsyncSession:
    """Get database session from dependency injection"""
    from app.database import get_db
    async for session in get_db():
        return session


async def get_user_watched_item_ids(db: AsyncSession, user_id: int) -> Set[int]:
    """Get set of item IDs that user is watching"""
    query = select(UserWatchlistItem.item_id).where(UserWatchlistItem.user_id == user_id)
    result = await db.execute(query)
    return set(result.scalars().all())


@strawberry.type
class Query:
    @strawberry.field
    async def auction_items(
        self,
        info: Info,
        page: int = 1,
        page_size: int = 20,
        auction_house: Optional[str] = None,
        category: Optional[str] = None,
        grading_company: Optional[str] = None,
        sport: Optional[str] = None,
        search: Optional[str] = None,
        min_bid: Optional[float] = None,
        max_bid: Optional[float] = None,
        status: str = "Live",
    ) -> PaginatedAuctionItems:
        """
        Get paginated list of auction items with filtering

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            auction_house: Filter by auction house (goldin, fanatics, etc.)
            category: Filter by category (Basketball, Baseball, etc.)
            grading_company: Filter by grading company (PSA, BGS, etc.)
            sport: Filter by sport (BASKETBALL, BASEBALL, FOOTBALL, etc.)
            search: Search in title and description
            min_bid: Minimum current bid
            max_bid: Maximum current bid
            status: Filter by status (default: Live)
        """
        db = await get_db_session()

        # Get current user from context (may be None)
        user = info.context.get("user") if info.context else None

        # Build query
        query = select(AuctionItemModel)

        # Apply filters
        filters = []
        if status:
            filters.append(AuctionItemModel.status == status)
            # Also filter out items where end_time has passed (actually ended)
            if status == "Live":
                filters.append(AuctionItemModel.end_time > datetime.utcnow())
        if auction_house:
            filters.append(AuctionItemModel.auction_house == auction_house)
        if category:
            filters.append(AuctionItemModel.category == category)
        if grading_company:
            filters.append(AuctionItemModel.grading_company == grading_company)
        if sport:
            filters.append(AuctionItemModel.sport == sport)
        if min_bid is not None:
            filters.append(AuctionItemModel.current_bid >= min_bid)
        if max_bid is not None:
            filters.append(AuctionItemModel.current_bid <= max_bid)

        # Use FTS5 for fast full-text search
        fts_ids: Optional[Set[int]] = None
        if search:
            # Escape special FTS5 characters and build query
            fts_search = search.replace('"', '""').replace("'", "''")
            # Use FTS5 MATCH for fast full-text search
            fts_query = text(
                "SELECT rowid FROM auction_items_fts WHERE auction_items_fts MATCH :search"
            )
            try:
                fts_result = await db.execute(fts_query, {"search": f'"{fts_search}"'})
                fts_ids = set(row[0] for row in fts_result.fetchall())
                if fts_ids:
                    filters.append(AuctionItemModel.id.in_(fts_ids))
                else:
                    # No FTS matches, return empty result
                    return PaginatedAuctionItems(
                        items=[],
                        total=0,
                        page=page,
                        page_size=page_size,
                        has_more=False,
                    )
            except Exception:
                # Fallback to LIKE if FTS5 fails (e.g., table doesn't exist)
                search_filter = or_(
                    AuctionItemModel.title.ilike(f"%{search}%"),
                    AuctionItemModel.description.ilike(f"%{search}%"),
                )
                filters.append(search_filter)

        if filters:
            query = query.where(*filters)

        # Get total count
        count_query = select(func.count()).select_from(AuctionItemModel)
        if filters:
            count_query = count_query.where(*filters)
        result = await db.execute(count_query)
        total = result.scalar() or 0

        # Apply pagination and ordering
        offset = (page - 1) * page_size
        query = query.order_by(AuctionItemModel.end_time.asc()).offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()

        # Get user's watched item IDs for per-user is_watched
        watched_ids: Set[int] = set()
        if user:
            watched_ids = await get_user_watched_item_ids(db, user.id)

        # Convert to GraphQL types with per-user is_watched
        graphql_items = [
            auction_item_from_model(item, is_watched=(item.id in watched_ids))
            for item in items
        ]

        return PaginatedAuctionItems(
            items=graphql_items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(items)) < total,
        )

    @strawberry.field
    async def auction_item(self, id: int) -> Optional[AuctionItemType]:
        """Get a single auction item by ID"""
        db = await get_db_session()

        query = select(AuctionItemModel).where(AuctionItemModel.id == id)
        result = await db.execute(query)
        item = result.scalar_one_or_none()

        if item:
            return auction_item_from_model(item)
        return None

    @strawberry.field
    async def auctions(
        self,
        auction_house: Optional[str] = None,
        status: str = "active",
    ) -> List[AuctionType]:
        """Get list of auctions"""
        db = await get_db_session()

        query = select(AuctionModel)

        filters = []
        if auction_house:
            filters.append(AuctionModel.auction_house == auction_house)
        if status:
            filters.append(AuctionModel.status == status)

        if filters:
            query = query.where(*filters)

        result = await db.execute(query)
        auctions = result.scalars().all()

        return [auction_from_model(auction) for auction in auctions]

    @strawberry.field
    async def market_value_estimate(
        self,
        item_id: int,
    ) -> MarketValueEstimate:
        """
        Get market value estimate for an auction item.
        Returns cached value from DB if available, otherwise calls LLM and caches result.
        """
        from datetime import datetime

        db = await get_db_session()

        # Fetch the item
        query = select(AuctionItemModel).where(AuctionItemModel.id == item_id)
        result = await db.execute(query)
        item = result.scalar_one_or_none()

        if not item:
            return MarketValueEstimate(
                confidence="low",
                notes="Item not found",
            )

        # Check if we already have a cached market value estimate in the database
        if item.market_value_avg is not None:
            return MarketValueEstimate(
                estimated_low=item.market_value_low,
                estimated_high=item.market_value_high,
                estimated_average=item.market_value_avg,
                confidence=item.market_value_confidence or "medium",
                notes=item.market_value_notes or "",
            )

        # No cached value - call LLM and save result
        try:
            estimator = MarketValueEstimator()
            estimate_dict = estimator.estimate_value(
                title=item.title,
                grading_company=item.grading_company,
                grade=item.grade,
                current_bid=item.current_bid,
            )

            # Save to database for future requests
            item.market_value_low = estimate_dict.get("estimated_low")
            item.market_value_high = estimate_dict.get("estimated_high")
            item.market_value_avg = estimate_dict.get("estimated_average")
            item.market_value_confidence = estimate_dict.get("confidence", "low")
            item.market_value_notes = estimate_dict.get("notes", "")
            item.market_value_updated_at = datetime.utcnow()
            await db.commit()

            return MarketValueEstimate(
                estimated_low=estimate_dict.get("estimated_low"),
                estimated_high=estimate_dict.get("estimated_high"),
                estimated_average=estimate_dict.get("estimated_average"),
                confidence=estimate_dict.get("confidence", "low"),
                notes=estimate_dict.get("notes", ""),
            )
        except Exception as e:
            return MarketValueEstimate(
                confidence="low",
                notes=f"Error estimating value: {str(e)}",
            )

    @strawberry.field
    async def auction_houses(self) -> List[str]:
        """Get list of unique auction houses"""
        db = await get_db_session()

        query = select(AuctionItemModel.auction_house).distinct()
        result = await db.execute(query)
        houses = result.scalars().all()

        return list(houses)

    @strawberry.field
    async def categories(self, auction_house: Optional[str] = None) -> List[str]:
        """Get list of unique categories"""
        db = await get_db_session()

        query = select(AuctionItemModel.category).distinct().where(
            AuctionItemModel.category.isnot(None)
        )

        if auction_house:
            query = query.where(AuctionItemModel.auction_house == auction_house)

        result = await db.execute(query)
        cats = result.scalars().all()

        return [c for c in cats if c]

    @strawberry.field
    async def watchlist(
        self,
        info: Info,
        include_ended: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedAuctionItems:
        """
        Get current user's watchlist items.
        Requires authentication.

        Args:
            include_ended: Include items from ended auctions (default True)
            page: Page number (1-indexed)
            page_size: Number of items per page
        """
        # Check for authenticated user
        user = info.context.get("user") if info.context else None
        if not user:
            return PaginatedAuctionItems(
                items=[],
                total=0,
                page=1,
                page_size=page_size,
                has_more=False,
            )

        db = await get_db_session()

        # Build query joining watchlist with auction items
        query = (
            select(AuctionItemModel)
            .join(UserWatchlistItem, UserWatchlistItem.item_id == AuctionItemModel.id)
            .where(UserWatchlistItem.user_id == user.id)
        )

        # Optionally filter out ended items
        if not include_ended:
            query = query.where(AuctionItemModel.end_time > datetime.utcnow())

        # Get total count
        count_query = (
            select(func.count())
            .select_from(AuctionItemModel)
            .join(UserWatchlistItem, UserWatchlistItem.item_id == AuctionItemModel.id)
            .where(UserWatchlistItem.user_id == user.id)
        )
        if not include_ended:
            count_query = count_query.where(AuctionItemModel.end_time > datetime.utcnow())

        result = await db.execute(count_query)
        total = result.scalar() or 0

        # Apply pagination and ordering (ending soonest first)
        offset = (page - 1) * page_size
        query = query.order_by(AuctionItemModel.end_time.asc()).offset(offset).limit(page_size)

        # Execute query
        result = await db.execute(query)
        items = result.scalars().all()

        # Convert to GraphQL types - all items in watchlist are watched by this user
        graphql_items = [auction_item_from_model(item, is_watched=True) for item in items]

        return PaginatedAuctionItems(
            items=graphql_items,
            total=total,
            page=page,
            page_size=page_size,
            has_more=(offset + len(items)) < total,
        )

    @strawberry.field
    async def price_history(
        self,
        item_id: int,
        days: int = 30,
    ) -> List[PriceSnapshotType]:
        """
        Get price history for an auction item.

        Args:
            item_id: ID of the auction item
            days: Number of days of history to fetch (default 30)
        """
        db = await get_db_session()
        service = PriceSnapshotService(db)

        snapshots = await service.get_price_history(item_id, days)

        return [
            PriceSnapshotType(
                snapshot_date=s.snapshot_date,
                current_bid=s.current_bid,
                bid_count=s.bid_count,
                status=s.status
            )
            for s in snapshots
        ]
