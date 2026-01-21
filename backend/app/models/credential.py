"""
Encrypted credential storage for auction house logins
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class AuctionHouseCredential(Base):
    """Encrypted credentials for auction house login"""
    __tablename__ = "auction_house_credentials"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key to user
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Auction house identifier
    auction_house: Mapped[str] = mapped_column(String(50), index=True)  # 'goldin', 'fanatics', etc.

    # Encrypted credentials (AES-256)
    encrypted_username: Mapped[str] = mapped_column(Text)  # Email/username
    encrypted_password: Mapped[str] = mapped_column(Text)
    encryption_iv: Mapped[str] = mapped_column(String(64))  # Initialization vectors (combined)

    # Session state (encrypted)
    encrypted_session_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)  # False if login failed
    last_verified: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="auction_house_credentials")
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession",
        back_populates="credential",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('ix_user_auction_house', 'user_id', 'auction_house', unique=True),
    )


class UserSession(Base):
    """Active browser sessions for auction houses"""
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)

    credential_id: Mapped[int] = mapped_column(ForeignKey("auction_house_credentials.id"), index=True)

    # Session data (encrypted JSON with cookies, localStorage, etc.)
    encrypted_browser_state: Mapped[str] = mapped_column(Text)
    encryption_iv: Mapped[str] = mapped_column(String(32))

    # Validity
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationship
    credential: Mapped["AuctionHouseCredential"] = relationship(
        "AuctionHouseCredential",
        back_populates="sessions"
    )
