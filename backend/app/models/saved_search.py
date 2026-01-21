"""
Saved search model for persisting user search configurations
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class SavedSearch(Base):
    """User's saved search configurations"""
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Foreign key
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # Search metadata
    name: Mapped[str] = mapped_column(String(100))

    # Filter configuration (stored as JSON)
    # Example: {"search": "jordan", "auctionHouse": "goldin", "minBid": 100, "maxBid": 1000}
    filters: Mapped[dict] = mapped_column(JSON)

    # Notifications (for future email alerts feature)
    email_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_alert_sent: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="saved_searches")
