"""
GraphQL Mutations
Define all write operations for the API
"""
import strawberry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from strawberry.types import Info

from app.models import AuctionItem as AuctionItemModel, UserWatchlistItem
from app.graphql.types import GenericResponse


async def get_db_session() -> AsyncSession:
    """Get database session from dependency injection"""
    from app.database import get_db
    async for session in get_db():
        return session


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def toggle_watch(
        self,
        info: Info,
        item_id: int,
    ) -> GenericResponse:
        """
        Toggle watch status on an auction item for the current user.
        Requires authentication.

        Args:
            item_id: ID of the auction item
        """
        # Check for authenticated user
        user = info.context.get("user") if info.context else None
        if not user:
            return GenericResponse(
                success=False,
                message="Authentication required to watch items",
            )

        db = await get_db_session()

        try:
            # Check if item exists
            item_query = select(AuctionItemModel).where(AuctionItemModel.id == item_id)
            result = await db.execute(item_query)
            item = result.scalar_one_or_none()

            if not item:
                return GenericResponse(
                    success=False,
                    message=f"Item with ID {item_id} not found",
                )

            # Check if user already has this item in their watchlist
            watchlist_query = select(UserWatchlistItem).where(
                UserWatchlistItem.user_id == user.id,
                UserWatchlistItem.item_id == item_id
            )
            result = await db.execute(watchlist_query)
            existing = result.scalar_one_or_none()

            if existing:
                # Remove from watchlist
                await db.delete(existing)
                await db.commit()
                return GenericResponse(
                    success=True,
                    message="Removed from watchlist",
                )
            else:
                # Add to watchlist
                watchlist_item = UserWatchlistItem(
                    user_id=user.id,
                    item_id=item_id
                )
                db.add(watchlist_item)
                await db.commit()
                return GenericResponse(
                    success=True,
                    message="Added to watchlist",
                )

        except Exception as e:
            await db.rollback()
            return GenericResponse(
                success=False,
                message=f"Error toggling watch: {str(e)}",
            )
