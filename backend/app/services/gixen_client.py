"""
Gixen API client for eBay auction sniping.

Gixen API endpoint: https://www.gixen.com/api.php
Auth via query params: ?username=X&password=Y&notags=1
"""
import asyncio
import logging
from typing import Optional
from datetime import datetime

import httpx

from app.scrapers.base import retry_async

logger = logging.getLogger(__name__)

GIXEN_API_URL = "https://www.gixen.com/api.php"

# Rate limit: 1 request per second
_last_request_time = 0.0
_rate_lock = asyncio.Lock()


async def _rate_limit():
    """Enforce 1 request per second to Gixen API."""
    global _last_request_time
    async with _rate_lock:
        now = asyncio.get_event_loop().time()
        elapsed = now - _last_request_time
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _last_request_time = asyncio.get_event_loop().time()


class GixenClient:
    """Python wrapper for the Gixen sniping API."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    def _base_params(self) -> dict:
        return {
            "username": self.username,
            "password": self.password,
            "notags": "1",
        }

    @retry_async(max_retries=2, delay=2.0)
    async def _request(self, extra_params: dict) -> str:
        """Make a rate-limited request to Gixen API."""
        await _rate_limit()
        params = {**self._base_params(), **extra_params}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(GIXEN_API_URL, params=params)
            response.raise_for_status()
            return response.text.strip()

    async def add_snipe(self, item_id: str, max_bid: float, bid_offset: int = 6) -> dict:
        """
        Add a snipe to Gixen.

        Args:
            item_id: eBay item ID
            max_bid: Maximum bid amount
            bid_offset: Seconds before auction end to place bid (3/6/8/10/15)

        Returns:
            dict with 'success', 'message', and 'raw' response
        """
        result = await self._request({
            "itemid": item_id,
            "maxbid": f"{max_bid:.2f}",
            "snipeoffset": str(bid_offset),
        })

        logger.info(f"Gixen add_snipe({item_id}, ${max_bid}): {result}")

        success = "ADDED" in result.upper() or "OK" in result.upper()
        return {
            "success": success,
            "message": result,
            "raw": result,
        }

    async def delete_snipe(self, item_id: str) -> dict:
        """
        Delete a snipe from Gixen.

        Returns:
            dict with 'success', 'message', and 'raw' response
        """
        result = await self._request({
            "ditemid": item_id,
        })

        logger.info(f"Gixen delete_snipe({item_id}): {result}")

        success = "DELETED" in result.upper() or "OK" in result.upper()
        return {
            "success": success,
            "message": result,
            "raw": result,
        }

    async def list_snipes(self, mirror: bool = False) -> list[dict]:
        """
        List all snipes on Gixen.

        Args:
            mirror: If True, use mirror server

        Returns:
            List of snipe dicts with keys: item_id, max_bid, end_time, status, etc.
        """
        params = {"listsnipesmain" if not mirror else "listsnipesmirror": "1"}
        result = await self._request(params)

        if not result or "ERROR" in result.upper():
            logger.warning(f"Gixen list_snipes error: {result}")
            return []

        snipes = []
        for line in result.split("\n"):
            line = line.strip()
            if not line or line.startswith("<!--") or line.startswith("OK"):
                continue

            # Gixen returns pipe-delimited data:
            # item_id|max_bid|end_time_unix|offset|status|...
            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    snipe = {
                        "item_id": parts[0].strip(),
                        "max_bid": float(parts[1].strip()) if len(parts) > 1 else 0.0,
                    }
                    if len(parts) > 2 and parts[2].strip():
                        try:
                            snipe["end_time"] = datetime.fromtimestamp(int(parts[2].strip()))
                        except (ValueError, OSError):
                            snipe["end_time"] = None
                    if len(parts) > 3:
                        snipe["offset"] = parts[3].strip()
                    if len(parts) > 4:
                        snipe["status"] = parts[4].strip()
                    snipes.append(snipe)
                except (ValueError, IndexError) as e:
                    logger.debug(f"Skipping unparseable Gixen line: {line} ({e})")

        logger.info(f"Gixen list_snipes: {len(snipes)} snipes found")
        return snipes

    async def list_completed(self) -> list[dict]:
        """
        List completed (won/lost) snipes on Gixen.

        Returns:
            List of completed snipe dicts
        """
        params = {"listsnipescompleted": "1"}
        result = await self._request(params)

        if not result or "ERROR" in result.upper():
            return []

        completed = []
        for line in result.split("\n"):
            line = line.strip()
            if not line or line.startswith("<!--") or line.startswith("OK"):
                continue

            parts = line.split("|")
            if len(parts) >= 3:
                try:
                    entry = {
                        "item_id": parts[0].strip(),
                        "max_bid": float(parts[1].strip()) if len(parts) > 1 else 0.0,
                    }
                    if len(parts) > 2:
                        entry["final_price"] = float(parts[2].strip()) if parts[2].strip() else None
                    if len(parts) > 3:
                        entry["won"] = parts[3].strip().upper() in ("WON", "1", "TRUE")
                    if len(parts) > 4:
                        entry["status"] = parts[4].strip()
                    completed.append(entry)
                except (ValueError, IndexError) as e:
                    logger.debug(f"Skipping unparseable completed line: {line} ({e})")

        return completed

    async def purge_completed(self) -> dict:
        """
        Purge completed snipes from Gixen.

        Returns:
            dict with 'success' and 'message'
        """
        result = await self._request({"purgecompleted": "1"})
        logger.info(f"Gixen purge_completed: {result}")

        success = "COMPLETEDPURGED" in result.upper() or "OK" in result.upper()
        return {
            "success": success,
            "message": result,
        }

    async def verify_credentials(self) -> dict:
        """
        Verify Gixen credentials by making a list_snipes call.

        Returns:
            dict with 'valid' bool and 'message'
        """
        try:
            result = await self._request({"listsnipesmain": "1"})

            if "ERROR" in result.upper() and ("LOGIN" in result.upper() or "AUTH" in result.upper() or "PASSWORD" in result.upper()):
                return {"valid": False, "message": result}

            return {"valid": True, "message": "Credentials verified"}
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                return {"valid": False, "message": "Invalid credentials"}
            return {"valid": False, "message": str(e)}
        except Exception as e:
            return {"valid": False, "message": f"Connection error: {e}"}
