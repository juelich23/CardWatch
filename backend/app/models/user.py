"""
User model for multi-user authentication
"""
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.credential import AuctionHouseCredential
    from app.models.watchlist import UserWatchlistItem
    from app.models.saved_search import SavedSearch


class User(Base):
    """User account for the CardWatch platform"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Authentication
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))

    # Profile
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    auction_house_credentials: Mapped[List["AuctionHouseCredential"]] = relationship(
        "AuctionHouseCredential",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    watchlist_items: Mapped[List["UserWatchlistItem"]] = relationship(
        "UserWatchlistItem",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    saved_searches: Mapped[List["SavedSearch"]] = relationship(
        "SavedSearch",
        back_populates="user",
        cascade="all, delete-orphan"
    )
