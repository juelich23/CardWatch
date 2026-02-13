"""
Bidding models for automated eBay auction sniping via Gixen
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.auction import AuctionItem


class BiddingRule(Base):
    """User-defined auto-bidding criteria for eBay auctions"""
    __tablename__ = "bidding_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Rule metadata
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Title matching
    title_contains: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # comma-separated, AND logic
    title_excludes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # comma-separated, OR logic

    # Card filters
    sport: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    grading_company: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    min_grade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_grade: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    item_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Bid configuration
    max_bid: Mapped[float] = mapped_column(Float)  # hard ceiling
    bid_strategy: Mapped[str] = mapped_column(String(30), default="fixed")  # fixed / current_plus_pct / market_value_pct
    bid_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # percentage for pct strategies

    # Safety limits
    max_active_snipes: Mapped[int] = mapped_column(Integer, default=10)
    max_current_bid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_end_hours: Mapped[float] = mapped_column(Float, default=1.0)  # won't match items ending within this
    max_end_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Gixen settings
    bid_offset_seconds: Mapped[int] = mapped_column(Integer, default=6)  # 3/6/8/10/15

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="bidding_rules")
    snipes: Mapped[list["GixenSnipe"]] = relationship(
        "GixenSnipe",
        back_populates="rule",
        cascade="all, delete-orphan"
    )


class GixenSnipe(Base):
    """Individual snipe record submitted to Gixen"""
    __tablename__ = "gixen_snipes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign keys
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rule_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bidding_rules.id"), nullable=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("auction_items.id"), index=True)

    # Denormalized for Gixen API calls
    ebay_item_id: Mapped[str] = mapped_column(String(50), index=True)

    # Bid details
    max_bid: Mapped[float] = mapped_column(Float)
    bid_offset_seconds: Mapped[int] = mapped_column(Integer, default=6)
    current_bid_at_snipe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Status tracking
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # pending -> submitted -> active -> won/lost/error/cancelled/expired

    # Gixen response data
    gixen_status: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    gixen_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Outcome
    final_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    won: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="gixen_snipes")
    rule: Mapped[Optional["BiddingRule"]] = relationship("BiddingRule", back_populates="snipes")
    item: Mapped["AuctionItem"] = relationship("AuctionItem")

    __table_args__ = (
        Index('ix_gixen_snipe_user_ebay', 'user_id', 'ebay_item_id', unique=True),
    )


class GixenCredential(Base):
    """Encrypted Gixen account credentials"""
    __tablename__ = "gixen_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)

    # Encrypted credentials (AES-256)
    encrypted_username: Mapped[str] = mapped_column(Text)
    encrypted_password: Mapped[str] = mapped_column(Text)
    encryption_iv: Mapped[str] = mapped_column(String(64))  # Combined IVs

    # Status
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="gixen_credential")
