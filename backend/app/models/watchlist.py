"""
Per-user watchlist model
"""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.auction import AuctionItem


class UserWatchlistItem(Base):
    """Per-user watchlist items - tracks which items each user is watching"""
    __tablename__ = "user_watchlist_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("auction_items.id"), index=True)

    # Timestamp
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="watchlist_items")
    item: Mapped["AuctionItem"] = relationship("AuctionItem", back_populates="watchers")

    __table_args__ = (
        Index('ix_user_watchlist_unique', 'user_id', 'item_id', unique=True),
    )
