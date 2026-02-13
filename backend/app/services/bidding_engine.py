"""
Bidding engine: rule matching, bid calculation, snipe submission, and status sync.

Scheduled jobs:
- run_bidding_rules(): every 10 min - match rules to eBay items, create GixenSnipe rows
- submit_pending_snipes(): every 5 min - send pending snipes to Gixen API
- sync_gixen_status(): every 15 min - poll Gixen for outcomes (won/lost)
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auction import AuctionItem
from app.models.bidding import BiddingRule, GixenSnipe, GixenCredential
from app.services.encryption import get_encryption_service
from app.services.gixen_client import GixenClient

logger = logging.getLogger(__name__)


def item_matches_rule(item: AuctionItem, rule: BiddingRule) -> bool:
    """Check if an auction item matches a bidding rule's criteria."""
    title = (item.title or "").lower()

    # Title contains (AND logic - all terms must be present)
    if rule.title_contains:
        terms = [t.strip().lower() for t in rule.title_contains.split(",") if t.strip()]
        if terms and not all(term in title for term in terms):
            return False

    # Title excludes (OR logic - any excluded term disqualifies)
    if rule.title_excludes:
        excludes = [t.strip().lower() for t in rule.title_excludes.split(",") if t.strip()]
        if any(term in title for term in excludes):
            return False

    # Sport filter
    if rule.sport and item.sport:
        if rule.sport.lower() != item.sport.lower():
            return False
    elif rule.sport and not item.sport:
        return False

    # Grading company
    if rule.grading_company and item.grading_company:
        if rule.grading_company.lower() != item.grading_company.lower():
            return False
    elif rule.grading_company and not item.grading_company:
        return False

    # Grade range
    if item.grade:
        try:
            grade_val = float(item.grade)
            if rule.min_grade is not None and grade_val < rule.min_grade:
                return False
            if rule.max_grade is not None and grade_val > rule.max_grade:
                return False
        except (ValueError, TypeError):
            pass

    # Item type
    if rule.item_type and item.item_type:
        if rule.item_type.lower() != item.item_type.lower():
            return False
    elif rule.item_type and not item.item_type:
        return False

    # Category
    if rule.category and item.category:
        if rule.category.lower() != item.category.lower():
            return False
    elif rule.category and not item.category:
        return False

    # Max current bid filter
    if rule.max_current_bid is not None and item.current_bid is not None:
        if item.current_bid > rule.max_current_bid:
            return False

    # End time window
    if item.end_time:
        now = datetime.utcnow()
        hours_until_end = (item.end_time - now).total_seconds() / 3600

        if hours_until_end < rule.min_end_hours:
            return False
        if rule.max_end_hours is not None and hours_until_end > rule.max_end_hours:
            return False
    else:
        # No end time = can't bid on it
        return False

    return True


def calculate_bid_amount(item: AuctionItem, rule: BiddingRule) -> float:
    """Calculate bid amount based on rule strategy, capped at max_bid."""
    if rule.bid_strategy == "fixed":
        return rule.max_bid

    elif rule.bid_strategy == "current_plus_pct":
        current = item.current_bid or 0.0
        pct = rule.bid_pct or 10.0
        calculated = current * (1 + pct / 100)
        return min(calculated, rule.max_bid)

    elif rule.bid_strategy == "market_value_pct":
        market_val = item.market_value_avg
        if market_val and market_val > 0:
            pct = rule.bid_pct or 80.0
            calculated = market_val * (pct / 100)
            return min(calculated, rule.max_bid)
        # Fallback to max_bid if no market value
        return rule.max_bid

    return rule.max_bid


async def run_bidding_rules(user_id: Optional[int] = None):
    """
    Main rule matching entry point.
    Evaluates all active bidding rules against eBay auction items.
    Creates GixenSnipe rows for matches.
    """
    from app.services.scraper_jobs import get_db_session

    logger.info(f"Starting rule matching (user_id={user_id})")
    async_session = get_db_session()
    async with async_session() as db:
        try:
            # Get active rules
            query = select(BiddingRule).where(BiddingRule.is_active == True)
            if user_id:
                query = query.where(BiddingRule.user_id == user_id)
            result = await db.execute(query)
            rules = result.scalars().all()

            if not rules:
                logger.info("No active bidding rules found")
                return {"matched": 0, "created": 0}

            # Get active eBay items
            now = datetime.utcnow()
            items_result = await db.execute(
                select(AuctionItem).where(
                    AuctionItem.auction_house == "ebay",
                    AuctionItem.status.in_(["active", "Live"]),
                    AuctionItem.end_time > now,
                )
            )
            items = items_result.scalars().all()
            logger.info(f"Evaluating {len(rules)} rules against {len(items)} eBay items")

            # Track best bid per item (across all rules)
            # Key: (user_id, item_id), Value: (calculated_bid, rule, item)
            best_bids: dict[tuple[int, int], tuple[float, BiddingRule, AuctionItem]] = {}

            for rule in rules:
                # Check active snipe count for this rule
                active_count_result = await db.execute(
                    select(func.count(GixenSnipe.id)).where(
                        GixenSnipe.rule_id == rule.id,
                        GixenSnipe.status.in_(["pending", "submitted", "active"]),
                    )
                )
                active_count = active_count_result.scalar() or 0
                if active_count >= rule.max_active_snipes:
                    logger.debug(f"Rule {rule.id} '{rule.name}' at max active snipes ({active_count})")
                    continue

                remaining_slots = rule.max_active_snipes - active_count

                matches_for_rule = 0
                for item in items:
                    if matches_for_rule >= remaining_slots:
                        break

                    if not item_matches_rule(item, rule):
                        continue

                    bid_amount = calculate_bid_amount(item, rule)
                    if bid_amount <= 0:
                        continue

                    key = (rule.user_id, item.id)
                    if key not in best_bids or bid_amount > best_bids[key][0]:
                        best_bids[key] = (bid_amount, rule, item)
                    matches_for_rule += 1

            # Create snipes for best bids (deduplication: skip if snipe already exists)
            created = 0
            for (uid, item_id), (bid_amount, rule, item) in best_bids.items():
                existing = await db.execute(
                    select(GixenSnipe).where(
                        GixenSnipe.user_id == uid,
                        GixenSnipe.ebay_item_id == item.external_id,
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                snipe = GixenSnipe(
                    user_id=uid,
                    rule_id=rule.id,
                    item_id=item.id,
                    ebay_item_id=item.external_id,
                    max_bid=bid_amount,
                    bid_offset_seconds=rule.bid_offset_seconds,
                    current_bid_at_snipe=item.current_bid,
                    status="pending",
                )
                db.add(snipe)
                created += 1

            await db.commit()
            logger.info(f"Rule matching complete: {len(best_bids)} matches, {created} new snipes created")
            return {"matched": len(best_bids), "created": created}

        except Exception as e:
            logger.error(f"Rule matching failed: {e}")
            await db.rollback()
            raise


async def _get_gixen_client(db: AsyncSession, user_id: int) -> Optional[GixenClient]:
    """Get a GixenClient for a user by decrypting their stored credentials."""
    result = await db.execute(
        select(GixenCredential).where(GixenCredential.user_id == user_id)
    )
    cred = result.scalar_one_or_none()
    if not cred or not cred.is_valid:
        return None

    encryption = get_encryption_service()
    ivs = cred.encryption_iv.split("|")
    username = encryption.decrypt(cred.encrypted_username, ivs[0])
    password = encryption.decrypt(cred.encrypted_password, ivs[1] if len(ivs) > 1 else ivs[0])

    return GixenClient(username, password)


async def submit_pending_snipes():
    """
    Submit pending snipes to Gixen API.
    Skips items ending within 30 minutes (Gixen needs lead time).
    Marks items past end_time as expired.
    """
    from app.services.scraper_jobs import get_db_session

    logger.info("Starting pending snipe submission")
    async_session = get_db_session()
    async with async_session() as db:
        try:
            now = datetime.utcnow()
            cutoff = now + timedelta(minutes=30)

            # Get pending snipes with their items
            result = await db.execute(
                select(GixenSnipe).where(GixenSnipe.status == "pending")
            )
            pending = result.scalars().all()

            if not pending:
                logger.info("No pending snipes to submit")
                return {"submitted": 0, "expired": 0, "errors": 0}

            submitted = 0
            expired = 0
            errors = 0

            # Group by user for client reuse
            user_clients: dict[int, Optional[GixenClient]] = {}

            for snipe in pending:
                # Load the associated item
                item_result = await db.execute(
                    select(AuctionItem).where(AuctionItem.id == snipe.item_id)
                )
                item = item_result.scalar_one_or_none()

                # Mark expired if item has ended or ends too soon
                if item and item.end_time:
                    if item.end_time <= now:
                        snipe.status = "expired"
                        snipe.gixen_message = "Item ended before submission"
                        expired += 1
                        continue
                    if item.end_time <= cutoff:
                        snipe.status = "expired"
                        snipe.gixen_message = "Item ends within 30 minutes"
                        expired += 1
                        continue
                elif not item:
                    snipe.status = "error"
                    snipe.gixen_message = "Item not found in database"
                    errors += 1
                    continue

                # Get or create Gixen client for this user
                if snipe.user_id not in user_clients:
                    user_clients[snipe.user_id] = await _get_gixen_client(db, snipe.user_id)

                client = user_clients[snipe.user_id]
                if not client:
                    snipe.status = "error"
                    snipe.gixen_message = "No valid Gixen credentials"
                    errors += 1
                    continue

                # Submit to Gixen
                try:
                    response = await client.add_snipe(
                        item_id=snipe.ebay_item_id,
                        max_bid=snipe.max_bid,
                        bid_offset=snipe.bid_offset_seconds,
                    )
                    if response["success"]:
                        snipe.status = "submitted"
                        snipe.submitted_at = datetime.utcnow()
                        snipe.gixen_message = response["message"]
                        submitted += 1
                    else:
                        snipe.status = "error"
                        snipe.gixen_message = response["message"]
                        errors += 1
                except Exception as e:
                    snipe.status = "error"
                    snipe.gixen_message = str(e)
                    errors += 1

            await db.commit()
            logger.info(f"Snipe submission complete: {submitted} submitted, {expired} expired, {errors} errors")
            return {"submitted": submitted, "expired": expired, "errors": errors}

        except Exception as e:
            logger.error(f"Snipe submission failed: {e}")
            await db.rollback()
            raise


async def sync_gixen_status():
    """
    Poll Gixen for snipe outcomes. Updates submitted/active snipes with won/lost status.
    """
    from app.services.scraper_jobs import get_db_session

    logger.info("Starting Gixen status sync")
    async_session = get_db_session()
    async with async_session() as db:
        try:
            # Get all users who have submitted/active snipes
            user_result = await db.execute(
                select(GixenSnipe.user_id).where(
                    GixenSnipe.status.in_(["submitted", "active"])
                ).distinct()
            )
            user_ids = [row[0] for row in user_result.fetchall()]

            if not user_ids:
                logger.info("No active snipes to sync")
                return {"synced": 0}

            total_synced = 0

            for uid in user_ids:
                client = await _get_gixen_client(db, uid)
                if not client:
                    continue

                # Get active snipes from Gixen
                try:
                    gixen_snipes = await client.list_snipes()
                    gixen_ids = {s["item_id"] for s in gixen_snipes}

                    # Update submitted snipes that appear in Gixen -> active
                    snipes_result = await db.execute(
                        select(GixenSnipe).where(
                            GixenSnipe.user_id == uid,
                            GixenSnipe.status == "submitted",
                        )
                    )
                    for snipe in snipes_result.scalars().all():
                        if snipe.ebay_item_id in gixen_ids:
                            snipe.status = "active"
                            total_synced += 1

                    # Check completed snipes
                    completed = await client.list_completed()
                    completed_map = {c["item_id"]: c for c in completed}

                    active_result = await db.execute(
                        select(GixenSnipe).where(
                            GixenSnipe.user_id == uid,
                            GixenSnipe.status.in_(["submitted", "active"]),
                        )
                    )
                    for snipe in active_result.scalars().all():
                        if snipe.ebay_item_id in completed_map:
                            comp = completed_map[snipe.ebay_item_id]
                            snipe.won = comp.get("won", False)
                            snipe.status = "won" if snipe.won else "lost"
                            snipe.final_price = comp.get("final_price")
                            snipe.gixen_status = comp.get("status", "")
                            total_synced += 1
                        elif snipe.ebay_item_id not in gixen_ids:
                            # Not in active or completed - check if item ended
                            item_result = await db.execute(
                                select(AuctionItem).where(AuctionItem.id == snipe.item_id)
                            )
                            item = item_result.scalar_one_or_none()
                            if item and item.end_time and item.end_time < datetime.utcnow():
                                snipe.status = "lost"
                                snipe.gixen_message = "Item ended, not found in Gixen results"
                                total_synced += 1

                except Exception as e:
                    logger.error(f"Gixen sync failed for user {uid}: {e}")
                    continue

            await db.commit()
            logger.info(f"Gixen sync complete: {total_synced} snipes updated")
            return {"synced": total_synced}

        except Exception as e:
            logger.error(f"Gixen sync failed: {e}")
            await db.rollback()
            raise


async def test_rule_matching(rule_id: int, db: AsyncSession) -> list[dict]:
    """
    Dry-run: show matching eBay items for a rule without creating snipes.

    Returns list of matching item dicts with calculated bid amounts.
    """
    result = await db.execute(select(BiddingRule).where(BiddingRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        return []

    now = datetime.utcnow()
    items_result = await db.execute(
        select(AuctionItem).where(
            AuctionItem.auction_house == "ebay",
            AuctionItem.status.in_(["active", "Live"]),
            AuctionItem.end_time > now,
        )
    )
    items = items_result.scalars().all()

    matches = []
    for item in items:
        if item_matches_rule(item, rule):
            bid_amount = calculate_bid_amount(item, rule)
            matches.append({
                "item_id": item.id,
                "external_id": item.external_id,
                "title": item.title,
                "current_bid": item.current_bid,
                "end_time": item.end_time.isoformat() if item.end_time else None,
                "image_url": item.image_url,
                "calculated_bid": bid_amount,
            })

    return matches
