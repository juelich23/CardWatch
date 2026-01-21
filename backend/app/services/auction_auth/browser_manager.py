"""
Persistent browser session manager for authenticated contexts
"""
import asyncio
from typing import Optional, Dict, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from app.services.encryption import get_encryption_service


class BrowserSessionManager:
    """
    Manages persistent browser sessions for authenticated access.
    Keeps browser alive and reuses authenticated contexts.
    """

    _instance: Optional['BrowserSessionManager'] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[int, BrowserContext] = {}  # user_id -> context
        self.pages: Dict[int, Page] = {}  # user_id -> page
        self.encryption = get_encryption_service()
        self._initialized = False

    @classmethod
    async def get_instance(cls) -> 'BrowserSessionManager':
        """Get or create the singleton instance"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = BrowserSessionManager()
            if not cls._instance._initialized:
                await cls._instance._initialize()
            return cls._instance

    async def _initialize(self):
        """Initialize playwright and browser"""
        if self._initialized:
            return

        print("Initializing persistent browser session...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,
            channel="chrome",
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        self._initialized = True
        print("Browser session initialized")

    async def shutdown(self):
        """Cleanup browser resources"""
        async with self._lock:
            for context in self.contexts.values():
                try:
                    await context.close()
                except:
                    pass
            self.contexts.clear()
            self.pages.clear()

            if self.browser:
                try:
                    await self.browser.close()
                except:
                    pass
                self.browser = None

            if self.playwright:
                try:
                    await self.playwright.stop()
                except:
                    pass
                self.playwright = None

            self._initialized = False
            BrowserSessionManager._instance = None

    async def get_authenticated_context(
        self,
        user_id: int,
        session_data: dict
    ) -> Tuple[BrowserContext, Page]:
        """
        Get or create an authenticated context for a user.
        Reuses existing context if available.
        """
        # Check if we already have a valid context for this user
        if user_id in self.contexts:
            context = self.contexts[user_id]
            page = self.pages.get(user_id)
            if page and not page.is_closed():
                return context, page
            # Page is closed, create new one
            page = await context.new_page()
            self.pages[user_id] = page
            return context, page

        # Create new context with session
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )

        # Restore cookies
        if session_data.get("cookies"):
            await context.add_cookies(session_data["cookies"])

        # Create page and restore localStorage
        page = await context.new_page()

        if session_data.get("localStorage"):
            await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=15000)
            for key, value in session_data["localStorage"].items():
                await page.evaluate(
                    "(args) => localStorage.setItem(args.key, args.value)",
                    {"key": key, "value": value}
                )

        self.contexts[user_id] = context
        self.pages[user_id] = page
        return context, page

    async def invalidate_context(self, user_id: int):
        """Invalidate a user's context (e.g., on session expiry)"""
        if user_id in self.pages:
            try:
                page = self.pages[user_id]
                if not page.is_closed():
                    await page.close()
            except:
                pass
            del self.pages[user_id]

        if user_id in self.contexts:
            try:
                await self.contexts[user_id].close()
            except:
                pass
            del self.contexts[user_id]


# Global instance accessor
async def get_browser_manager() -> BrowserSessionManager:
    """Get the singleton browser manager instance"""
    return await BrowserSessionManager.get_instance()
