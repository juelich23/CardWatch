"""
Bidding REST API endpoints for Gixen snipe management.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models import User, AuctionItem
from app.models.bidding import BiddingRule, GixenSnipe, GixenCredential
from app.services.encryption import get_encryption_service
from app.services.gixen_client import GixenClient
from app.services.bidding_engine import (
    run_bidding_rules,
    submit_pending_snipes,
    sync_gixen_status,
    test_rule_matching,
)

router = APIRouter(prefix="/api/bidding", tags=["bidding"])


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class GixenCredentialCreate(BaseModel):
    username: str
    password: str


class GixenCredentialStatus(BaseModel):
    has_credentials: bool
    is_valid: bool | None = None
    last_verified: datetime | None = None
    last_error: str | None = None


class BiddingRuleCreate(BaseModel):
    name: str
    title_contains: str | None = None
    title_excludes: str | None = None
    sport: str | None = None
    grading_company: str | None = None
    min_grade: float | None = None
    max_grade: float | None = None
    item_type: str | None = None
    category: str | None = None
    max_bid: float
    bid_strategy: str = "fixed"
    bid_pct: float | None = None
    max_active_snipes: int = 10
    max_current_bid: float | None = None
    min_end_hours: float = 1.0
    max_end_hours: float | None = None
    bid_offset_seconds: int = 6


class BiddingRuleUpdate(BaseModel):
    name: str | None = None
    title_contains: str | None = None
    title_excludes: str | None = None
    sport: str | None = None
    grading_company: str | None = None
    min_grade: float | None = None
    max_grade: float | None = None
    item_type: str | None = None
    category: str | None = None
    max_bid: float | None = None
    bid_strategy: str | None = None
    bid_pct: float | None = None
    max_active_snipes: int | None = None
    max_current_bid: float | None = None
    min_end_hours: float | None = None
    max_end_hours: float | None = None
    bid_offset_seconds: int | None = None


class BiddingRuleResponse(BaseModel):
    id: int
    name: str
    is_active: bool
    title_contains: str | None
    title_excludes: str | None
    sport: str | None
    grading_company: str | None
    min_grade: float | None
    max_grade: float | None
    item_type: str | None
    category: str | None
    max_bid: float
    bid_strategy: str
    bid_pct: float | None
    max_active_snipes: int
    max_current_bid: float | None
    min_end_hours: float
    max_end_hours: float | None
    bid_offset_seconds: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SnipeCreate(BaseModel):
    item_id: int
    max_bid: float
    bid_offset_seconds: int = 6


class SnipeResponse(BaseModel):
    id: int
    user_id: int
    rule_id: int | None
    item_id: int
    ebay_item_id: str
    max_bid: float
    bid_offset_seconds: int
    current_bid_at_snipe: float | None
    status: str
    gixen_status: str | None
    gixen_message: str | None
    final_price: float | None
    won: bool | None
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    # Joined item info
    item_title: str | None = None
    item_image_url: str | None = None
    item_end_time: datetime | None = None
    rule_name: str | None = None

    class Config:
        from_attributes = True


class SnipeStats(BaseModel):
    total: int
    pending: int
    submitted: int
    active: int
    won: int
    lost: int
    error: int
    expired: int
    cancelled: int
    win_rate: float | None
    total_spent: float


# ─── Gixen Credentials ───────────────────────────────────────────────────────

@router.post("/gixen-credentials")
async def store_gixen_credentials(
    request: GixenCredentialCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Store encrypted Gixen credentials."""
    encryption = get_encryption_service()

    enc_username, iv_username = encryption.encrypt(request.username)
    enc_password, iv_password = encryption.encrypt(request.password)
    combined_iv = f"{iv_username}|{iv_password}"

    result = await db.execute(
        select(GixenCredential).where(GixenCredential.user_id == user.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_username = enc_username
        existing.encrypted_password = enc_password
        existing.encryption_iv = combined_iv
        existing.is_valid = True
        existing.last_error = None
        existing.updated_at = datetime.utcnow()
    else:
        cred = GixenCredential(
            user_id=user.id,
            encrypted_username=enc_username,
            encrypted_password=enc_password,
            encryption_iv=combined_iv,
        )
        db.add(cred)

    await db.commit()
    return {"message": "Gixen credentials stored"}


@router.get("/gixen-credentials/status", response_model=GixenCredentialStatus)
async def get_gixen_credential_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if user has Gixen credentials and their validity."""
    result = await db.execute(
        select(GixenCredential).where(GixenCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()

    if not cred:
        return GixenCredentialStatus(has_credentials=False)

    return GixenCredentialStatus(
        has_credentials=True,
        is_valid=cred.is_valid,
        last_verified=cred.last_verified,
        last_error=cred.last_error,
    )


@router.delete("/gixen-credentials")
async def delete_gixen_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete stored Gixen credentials."""
    result = await db.execute(
        select(GixenCredential).where(GixenCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="No Gixen credentials found")

    await db.delete(cred)
    await db.commit()
    return {"message": "Gixen credentials deleted"}


@router.post("/gixen-credentials/verify")
async def verify_gixen_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Test Gixen credentials against the Gixen API."""
    result = await db.execute(
        select(GixenCredential).where(GixenCredential.user_id == user.id)
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="No Gixen credentials found")

    encryption = get_encryption_service()
    ivs = cred.encryption_iv.split("|")
    username = encryption.decrypt(cred.encrypted_username, ivs[0])
    password = encryption.decrypt(cred.encrypted_password, ivs[1] if len(ivs) > 1 else ivs[0])

    client = GixenClient(username, password)
    verification = await client.verify_credentials()

    cred.is_valid = verification["valid"]
    cred.last_verified = datetime.utcnow()
    if not verification["valid"]:
        cred.last_error = verification["message"]
    else:
        cred.last_error = None
    await db.commit()

    return verification


# ─── Bidding Rules ────────────────────────────────────────────────────────────

@router.get("/rules", response_model=List[BiddingRuleResponse])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's bidding rules."""
    result = await db.execute(
        select(BiddingRule)
        .where(BiddingRule.user_id == user.id)
        .order_by(BiddingRule.created_at.desc())
    )
    return result.scalars().all()


@router.post("/rules", response_model=BiddingRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: BiddingRuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new bidding rule."""
    if request.bid_offset_seconds not in (3, 6, 8, 10, 15):
        raise HTTPException(status_code=400, detail="bid_offset_seconds must be 3, 6, 8, 10, or 15")

    if request.bid_strategy not in ("fixed", "current_plus_pct", "market_value_pct"):
        raise HTTPException(status_code=400, detail="Invalid bid_strategy")

    rule = BiddingRule(
        user_id=user.id,
        **request.model_dump(),
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule


@router.put("/rules/{rule_id}", response_model=BiddingRuleResponse)
async def update_rule(
    rule_id: int,
    request: BiddingRuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a bidding rule."""
    result = await db.execute(
        select(BiddingRule).where(
            BiddingRule.id == rule_id,
            BiddingRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = request.model_dump(exclude_unset=True)

    if "bid_offset_seconds" in update_data and update_data["bid_offset_seconds"] not in (3, 6, 8, 10, 15):
        raise HTTPException(status_code=400, detail="bid_offset_seconds must be 3, 6, 8, 10, or 15")

    if "bid_strategy" in update_data and update_data["bid_strategy"] not in ("fixed", "current_plus_pct", "market_value_pct"):
        raise HTTPException(status_code=400, detail="Invalid bid_strategy")

    for key, value in update_data.items():
        setattr(rule, key, value)

    rule.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a bidding rule."""
    result = await db.execute(
        select(BiddingRule).where(
            BiddingRule.id == rule_id,
            BiddingRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"message": "Rule deleted"}


@router.post("/rules/{rule_id}/toggle")
async def toggle_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a rule's active status."""
    result = await db.execute(
        select(BiddingRule).where(
            BiddingRule.id == rule_id,
            BiddingRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.is_active = not rule.is_active
    rule.updated_at = datetime.utcnow()
    await db.commit()
    return {"is_active": rule.is_active}


@router.post("/rules/{rule_id}/test")
async def test_rule(
    rule_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dry-run: show matching eBay items without creating snipes."""
    result = await db.execute(
        select(BiddingRule).where(
            BiddingRule.id == rule_id,
            BiddingRule.user_id == user.id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    matches = await test_rule_matching(rule_id, db)
    return {"matches": matches, "count": len(matches)}


# ─── Snipes ───────────────────────────────────────────────────────────────────

@router.get("/snipes", response_model=List[SnipeResponse])
async def list_snipes(
    status_filter: Optional[str] = None,
    rule_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List snipes with optional filters."""
    query = select(GixenSnipe).where(GixenSnipe.user_id == user.id)

    if status_filter:
        query = query.where(GixenSnipe.status == status_filter)
    if rule_id:
        query = query.where(GixenSnipe.rule_id == rule_id)

    query = query.order_by(GixenSnipe.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    snipes = result.scalars().all()

    # Enrich with item and rule info
    responses = []
    for snipe in snipes:
        item_result = await db.execute(
            select(AuctionItem).where(AuctionItem.id == snipe.item_id)
        )
        item = item_result.scalar_one_or_none()

        rule_name = None
        if snipe.rule_id:
            rule_result = await db.execute(
                select(BiddingRule.name).where(BiddingRule.id == snipe.rule_id)
            )
            rule_name = rule_result.scalar_one_or_none()

        responses.append(SnipeResponse(
            id=snipe.id,
            user_id=snipe.user_id,
            rule_id=snipe.rule_id,
            item_id=snipe.item_id,
            ebay_item_id=snipe.ebay_item_id,
            max_bid=snipe.max_bid,
            bid_offset_seconds=snipe.bid_offset_seconds,
            current_bid_at_snipe=snipe.current_bid_at_snipe,
            status=snipe.status,
            gixen_status=snipe.gixen_status,
            gixen_message=snipe.gixen_message,
            final_price=snipe.final_price,
            won=snipe.won,
            created_at=snipe.created_at,
            updated_at=snipe.updated_at,
            submitted_at=snipe.submitted_at,
            item_title=item.title if item else None,
            item_image_url=item.image_url if item else None,
            item_end_time=item.end_time if item else None,
            rule_name=rule_name,
        ))

    return responses


@router.post("/snipes", response_model=SnipeResponse, status_code=status.HTTP_201_CREATED)
async def create_manual_snipe(
    request: SnipeCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a manual snipe (bypasses rules)."""
    # Get the item
    item_result = await db.execute(
        select(AuctionItem).where(AuctionItem.id == request.item_id)
    )
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if item.auction_house != "ebay":
        raise HTTPException(status_code=400, detail="Only eBay items can be sniped via Gixen")

    if request.bid_offset_seconds not in (3, 6, 8, 10, 15):
        raise HTTPException(status_code=400, detail="bid_offset_seconds must be 3, 6, 8, 10, or 15")

    # Check for duplicate
    existing = await db.execute(
        select(GixenSnipe).where(
            GixenSnipe.user_id == user.id,
            GixenSnipe.ebay_item_id == item.external_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Snipe already exists for this item")

    snipe = GixenSnipe(
        user_id=user.id,
        item_id=item.id,
        ebay_item_id=item.external_id,
        max_bid=request.max_bid,
        bid_offset_seconds=request.bid_offset_seconds,
        current_bid_at_snipe=item.current_bid,
        status="pending",
    )
    db.add(snipe)
    await db.commit()
    await db.refresh(snipe)

    return SnipeResponse(
        id=snipe.id,
        user_id=snipe.user_id,
        rule_id=snipe.rule_id,
        item_id=snipe.item_id,
        ebay_item_id=snipe.ebay_item_id,
        max_bid=snipe.max_bid,
        bid_offset_seconds=snipe.bid_offset_seconds,
        current_bid_at_snipe=snipe.current_bid_at_snipe,
        status=snipe.status,
        gixen_status=snipe.gixen_status,
        gixen_message=snipe.gixen_message,
        final_price=snipe.final_price,
        won=snipe.won,
        created_at=snipe.created_at,
        updated_at=snipe.updated_at,
        submitted_at=snipe.submitted_at,
        item_title=item.title,
        item_image_url=item.image_url,
        item_end_time=item.end_time,
    )


@router.delete("/snipes/{snipe_id}")
async def cancel_snipe(
    snipe_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a snipe. Calls Gixen delete if already submitted."""
    result = await db.execute(
        select(GixenSnipe).where(
            GixenSnipe.id == snipe_id,
            GixenSnipe.user_id == user.id,
        )
    )
    snipe = result.scalar_one_or_none()
    if not snipe:
        raise HTTPException(status_code=404, detail="Snipe not found")

    if snipe.status in ("won", "lost"):
        raise HTTPException(status_code=400, detail="Cannot cancel a completed snipe")

    # If already submitted to Gixen, delete from there too
    if snipe.status in ("submitted", "active"):
        cred_result = await db.execute(
            select(GixenCredential).where(GixenCredential.user_id == user.id)
        )
        cred = cred_result.scalar_one_or_none()
        if cred and cred.is_valid:
            encryption = get_encryption_service()
            ivs = cred.encryption_iv.split("|")
            username = encryption.decrypt(cred.encrypted_username, ivs[0])
            password = encryption.decrypt(cred.encrypted_password, ivs[1] if len(ivs) > 1 else ivs[0])
            client = GixenClient(username, password)
            try:
                await client.delete_snipe(snipe.ebay_item_id)
            except Exception as e:
                # Log but don't fail - still cancel locally
                import logging
                logging.getLogger(__name__).warning(f"Failed to delete snipe from Gixen: {e}")

    snipe.status = "cancelled"
    snipe.updated_at = datetime.utcnow()
    await db.commit()
    return {"message": "Snipe cancelled"}


@router.get("/snipes/stats", response_model=SnipeStats)
async def get_snipe_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get snipe statistics for the current user."""
    base = select(func.count(GixenSnipe.id)).where(GixenSnipe.user_id == user.id)

    total = (await db.execute(base)).scalar() or 0
    pending = (await db.execute(base.where(GixenSnipe.status == "pending"))).scalar() or 0
    submitted = (await db.execute(base.where(GixenSnipe.status == "submitted"))).scalar() or 0
    active = (await db.execute(base.where(GixenSnipe.status == "active"))).scalar() or 0
    won = (await db.execute(base.where(GixenSnipe.status == "won"))).scalar() or 0
    lost = (await db.execute(base.where(GixenSnipe.status == "lost"))).scalar() or 0
    error = (await db.execute(base.where(GixenSnipe.status == "error"))).scalar() or 0
    expired = (await db.execute(base.where(GixenSnipe.status == "expired"))).scalar() or 0
    cancelled = (await db.execute(base.where(GixenSnipe.status == "cancelled"))).scalar() or 0

    completed = won + lost
    win_rate = (won / completed * 100) if completed > 0 else None

    # Total spent on won items
    spent_result = await db.execute(
        select(func.sum(GixenSnipe.final_price)).where(
            GixenSnipe.user_id == user.id,
            GixenSnipe.status == "won",
            GixenSnipe.final_price.isnot(None),
        )
    )
    total_spent = spent_result.scalar() or 0.0

    return SnipeStats(
        total=total,
        pending=pending,
        submitted=submitted,
        active=active,
        won=won,
        lost=lost,
        error=error,
        expired=expired,
        cancelled=cancelled,
        win_rate=win_rate,
        total_spent=total_spent,
    )


# ─── Actions ─────────────────────────────────────────────────────────────────

@router.post("/run-rules")
async def trigger_run_rules(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Manually trigger rule matching for the current user."""
    background_tasks.add_task(run_bidding_rules, user_id=user.id)
    return {"message": "Rule matching triggered"}


@router.post("/sync-gixen")
async def trigger_sync_gixen(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Manually trigger Gixen status sync."""
    background_tasks.add_task(sync_gixen_status)
    return {"message": "Gixen sync triggered"}


@router.post("/submit-pending")
async def trigger_submit_pending(
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
):
    """Manually trigger submission of pending snipes."""
    background_tasks.add_task(submit_pending_snipes)
    return {"message": "Pending snipe submission triggered"}


# ─── eBay Item Upload (for local scraper) ────────────────────────────────────

class EbayItemUpload(BaseModel):
    external_id: str
    title: str
    description: str = ""
    category: str | None = None
    sport: str | None = None
    grading_company: str | None = None
    grade: str | None = None
    cert_number: str | None = None
    sub_category: str | None = None
    image_url: str | None = None
    current_bid: float | None = None
    starting_bid: float | None = None
    bid_count: int = 0
    end_time: str | None = None
    status: str = "Live"
    item_url: str | None = None
    lot_number: str | None = None
    item_type: str | None = None


@router.post("/upload-ebay-items")
async def upload_ebay_items(
    items: List[EbayItemUpload],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept scraped eBay items from a local scraper and save to DB."""
    from app.models import Auction

    # Get or create the ebay auction record
    result = await db.execute(
        select(Auction).where(
            Auction.auction_house == "ebay",
            Auction.external_id == "ebay-auctions",
        )
    )
    auction = result.scalar_one_or_none()
    if not auction:
        auction = Auction(
            auction_house="ebay",
            external_id="ebay-auctions",
            title="eBay Auctions",
            status="active",
        )
        db.add(auction)
        await db.flush()

    saved = 0
    updated = 0
    for item_data in items:
        # Parse end_time string to datetime
        end_time = None
        if item_data.end_time:
            try:
                end_time = datetime.fromisoformat(item_data.end_time.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        result = await db.execute(
            select(AuctionItem).where(
                AuctionItem.auction_house == "ebay",
                AuctionItem.external_id == item_data.external_id,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.title = item_data.title[:500]
            existing.current_bid = item_data.current_bid
            existing.bid_count = item_data.bid_count
            existing.end_time = end_time
            existing.status = item_data.status
            existing.image_url = item_data.image_url
            existing.item_url = item_data.item_url
            existing.grading_company = item_data.grading_company
            existing.grade = item_data.grade
            existing.cert_number = item_data.cert_number
            existing.sport = item_data.sport
            existing.category = item_data.category
            existing.item_type = item_data.item_type
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            db_item = AuctionItem(
                auction_id=auction.id,
                auction_house="ebay",
                external_id=item_data.external_id,
                title=item_data.title[:500],
                description=item_data.description,
                category=item_data.category,
                sport=item_data.sport,
                grading_company=item_data.grading_company,
                grade=item_data.grade,
                cert_number=item_data.cert_number,
                sub_category=item_data.sub_category,
                image_url=item_data.image_url,
                current_bid=item_data.current_bid,
                starting_bid=item_data.starting_bid,
                bid_count=item_data.bid_count,
                end_time=end_time,
                status=item_data.status,
                item_url=item_data.item_url,
                lot_number=item_data.lot_number,
                item_type=item_data.item_type,
            )
            db.add(db_item)
            saved += 1

    await db.commit()
    return {"message": f"Uploaded {saved} new, {updated} updated eBay items"}
