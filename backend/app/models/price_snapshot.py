"""
Price snapshot model for historical price tracking
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.auction import AuctionItem


class PriceSnapshot(Base):
    """Daily price snapshots for auction items"""
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key
    item_id: Mapped[int] = mapped_column(ForeignKey("auction_items.id"), index=True)

    # Snapshot data
    current_bid: Mapped[Optional[float]] = mapped_column(Float)
    bid_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50))

    # Timestamp (date for daily snapshots)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime, index=True)

    # Relationship
    item: Mapped["AuctionItem"] = relationship("AuctionItem", back_populates="price_snapshots")

    __table_args__ = (
        Index('ix_price_snapshot_item_date', 'item_id', 'snapshot_date', unique=True),
    )
