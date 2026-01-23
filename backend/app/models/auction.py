from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, JSON, Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.watchlist import UserWatchlistItem
    from app.models.price_snapshot import PriceSnapshot


class Auction(Base):
    """Auction from any auction house"""
    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Source information
    auction_house: Mapped[str] = mapped_column(String(50), index=True)  # 'goldin', 'fanatics', etc.
    external_id: Mapped[str] = mapped_column(String(255), index=True)  # ID from auction house

    # Auction details
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)

    # Timing
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)  # active, ended, upcoming

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    items: Mapped[list["AuctionItem"]] = relationship(back_populates="auction", cascade="all, delete-orphan")

    __table_args__ = (
        Index('ix_auction_house_external_id', 'auction_house', 'external_id', unique=True),
    )


class AuctionItem(Base):
    """Individual item/lot in an auction"""
    __tablename__ = "auction_items"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key
    auction_id: Mapped[int] = mapped_column(ForeignKey("auctions.id"), index=True)

    # Source information
    auction_house: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    lot_number: Mapped[Optional[str]] = mapped_column(String(100))
    cert_number: Mapped[Optional[str]] = mapped_column(String(100))  # Grading cert number

    # Grading information
    sub_category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    grading_company: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    grade: Mapped[Optional[str]] = mapped_column(String(20))  # e.g., "8.5", "9", "10"

    # Item details
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    sport: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # Sport category
    # item_type: Mapped[Optional[str]] = mapped_column(String(20), index=True)  # CARD, MEMORABILIA, AUTOGRAPH, SEALED, OTHER - COMMENTED OUT: Add column to DB first via Supabase

    # Images
    image_url: Mapped[Optional[str]] = mapped_column(String(1000))
    image_urls: Mapped[Optional[list]] = mapped_column(JSON)  # Multiple images

    # Pricing
    current_bid: Mapped[Optional[float]] = mapped_column(Float, index=True)
    starting_bid: Mapped[Optional[float]] = mapped_column(Float)
    reserve_price: Mapped[Optional[float]] = mapped_column(Float)
    buy_now_price: Mapped[Optional[float]] = mapped_column(Float)
    bid_count: Mapped[int] = mapped_column(Integer, default=0)

    # Alt.xyz pricing data
    alt_price_estimate: Mapped[Optional[float]] = mapped_column(Float)
    alt_price_data: Mapped[Optional[dict]] = mapped_column(JSON)  # Raw pricing data from Alt

    # LLM Market Value Estimate (cached to avoid re-fetching)
    market_value_low: Mapped[Optional[float]] = mapped_column(Float)
    market_value_high: Mapped[Optional[float]] = mapped_column(Float)
    market_value_avg: Mapped[Optional[float]] = mapped_column(Float)
    market_value_confidence: Mapped[Optional[str]] = mapped_column(String(20))  # low/medium/high
    market_value_notes: Mapped[Optional[str]] = mapped_column(String(1000))
    market_value_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timing
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    is_watched: Mapped[bool] = mapped_column(Boolean, default=False)

    # Item URL
    item_url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Metadata
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)  # Store raw scrape data
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    auction: Mapped["Auction"] = relationship(back_populates="items")
    watchers: Mapped[list["UserWatchlistItem"]] = relationship(
        "UserWatchlistItem",
        back_populates="item",
        cascade="all, delete-orphan"
    )
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(
        "PriceSnapshot",
        back_populates="item",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_item_auction_house_external_id', 'auction_house', 'external_id', unique=True),
        Index('ix_auction_item_status_end_time', 'status', 'end_time'),
    )
