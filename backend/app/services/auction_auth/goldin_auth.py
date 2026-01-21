"""
Goldin auction house authentication via browser automation
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Tuple
from playwright.async_api import async_playwright, BrowserContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import AuctionHouseCredential, UserSession
from app.services.credential_manager import CredentialManager
from app.services.encryption import get_encryption_service


class GoldinAuthService:
    """Handle Goldin auction house authentication via browser automation"""

    LOGIN_URL = "https://goldin.co/signIn"  # Correct URL - /login is 404
    ACCOUNT_URL = "https://goldin.co/account"
    SESSION_DURATION = timedelta(hours=12)  # Session validity

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager(db)
        self.encryption = get_encryption_service()

    async def login(self, user_id: int) -> Tuple[bool, str]:
        """
        Perform Goldin login for a user.
        Goldin uses a two-step login flow:
        1. Enter email and click Continue
        2. Enter password and submit

        Returns:
            tuple of (success: bool, message: str)
        """
        # Get user's Goldin credentials
        credential = await self.credential_manager.get_credential(user_id, "goldin")
        if not credential:
            return False, "No Goldin credentials stored for this user"

        username, password = self.credential_manager.decrypt_credentials(credential)

        browser = None
        p = None
        try:
            p = await async_playwright().start()
            # Use system Chrome instead of bundled Chromium (more stable on macOS)
            browser = await p.chromium.launch(headless=True, channel="chrome")
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
            )
            page = await context.new_page()

            # Navigate to login page
            print(f"   Navigating to Goldin login...")
            await page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Accept cookies if present
            accept_btn = await page.query_selector('button:has-text("Accept")')
            if accept_btn:
                await accept_btn.click()
                await asyncio.sleep(1)

            # STEP 1: Enter email
            print(f"   Step 1: Entering email...")
            email_input = await page.query_selector('input[type="email"]')
            if not email_input:
                await self.credential_manager.mark_credential_invalid(
                    credential, "Could not find email input"
                )
                return False, "Could not find email input on page"

            await email_input.fill(username)
            await asyncio.sleep(1)

            # Click Continue button
            continue_btn = await page.query_selector('button:has-text("Continue")')
            if not continue_btn:
                await self.credential_manager.mark_credential_invalid(
                    credential, "Could not find Continue button"
                )
                return False, "Could not find Continue button"

            await continue_btn.click()
            await asyncio.sleep(3)  # Wait for password form to appear

            # STEP 2: Enter password
            print(f"   Step 2: Entering password...")
            password_input = await page.query_selector('input[type="password"]')
            if not password_input:
                # Check for error message (email not found)
                error_el = await page.query_selector('[role="alert"], .error, .text-red')
                if error_el:
                    error_text = await error_el.inner_text()
                    await self.credential_manager.mark_credential_invalid(credential, error_text)
                    return False, f"Login failed: {error_text}"

                await self.credential_manager.mark_credential_invalid(
                    credential, "Could not find password input after email step"
                )
                return False, "Could not find password input - email may not be registered"

            await password_input.fill(password)
            await asyncio.sleep(1)

            # Click Continue/Sign In button (Goldin uses "Continue" for both steps)
            submit_btn = await page.query_selector(
                'button:has-text("Continue"), button:has-text("Sign In"), button:has-text("Log In"), button[type="submit"]'
            )
            if not submit_btn:
                await self.credential_manager.mark_credential_invalid(
                    credential, "Could not find submit button"
                )
                return False, "Could not find submit button"

            await submit_btn.click()

            # Wait for navigation - check for success or error
            print(f"   Waiting for login result...")
            await asyncio.sleep(5)

            current_url = page.url
            print(f"   Current URL: {current_url}")

            # Check for error messages
            error_el = await page.query_selector(
                '[role="alert"], .error-message, .text-red-500, .text-danger'
            )
            if error_el:
                error_text = await error_el.inner_text()
                if error_text.strip():
                    await self.credential_manager.mark_credential_invalid(credential, error_text)
                    return False, f"Login failed: {error_text}"

            # Check if we're still on sign in page (login failed)
            if "signin" in current_url.lower() or "sign-in" in current_url.lower():
                await self.credential_manager.mark_credential_invalid(
                    credential, "Login failed - incorrect password"
                )
                return False, "Login failed - incorrect credentials"

            # If we got redirected away from signIn, login was likely successful
            print(f"   Login successful, saving session...")

            # Success - save session state
            cookies = await context.cookies()
            storage = await page.evaluate("() => JSON.stringify(localStorage)")

            session_data = {
                "cookies": cookies,
                "localStorage": json.loads(storage) if storage else {},
                "timestamp": datetime.utcnow().isoformat()
            }

            await self._save_session(credential, session_data)
            await self.credential_manager.mark_credential_verified(credential)

            return True, "Login successful"

        except Exception as e:
            try:
                await self.credential_manager.mark_credential_invalid(credential, str(e))
            except Exception:
                pass  # DB might be closed
            return False, f"Login error: {str(e)}"
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass  # Browser may already be closed
            if p:
                try:
                    await p.stop()
                except Exception:
                    pass

    async def _save_session(
        self,
        credential: AuctionHouseCredential,
        session_data: dict
    ):
        """Save encrypted session data"""
        session_json = json.dumps(session_data)
        encrypted_session, iv = self.encryption.encrypt(session_json)

        # Deactivate existing sessions
        result = await self.db.execute(
            select(UserSession).where(
                UserSession.credential_id == credential.id,
                UserSession.is_active == True
            )
        )
        for old_session in result.scalars().all():
            old_session.is_active = False

        # Create new session
        expires_at = datetime.utcnow() + self.SESSION_DURATION
        new_session = UserSession(
            credential_id=credential.id,
            encrypted_browser_state=encrypted_session,
            encryption_iv=iv,
            expires_at=expires_at,
        )
        self.db.add(new_session)
        await self.db.commit()

    async def get_active_session(self, user_id: int) -> Optional[UserSession]:
        """Get active session for user's Goldin account"""
        credential = await self.credential_manager.get_credential(user_id, "goldin")
        if not credential:
            return None

        result = await self.db.execute(
            select(UserSession).where(
                UserSession.credential_id == credential.id,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none()

    async def is_session_valid(self, user_id: int) -> bool:
        """Check if user has a valid Goldin session"""
        session = await self.get_active_session(user_id)
        return session is not None

    async def get_authenticated_context(
        self,
        user_id: int,
        playwright_instance
    ) -> Optional[BrowserContext]:
        """
        Get an authenticated browser context for Goldin

        Returns None if no valid session exists (requires login first)
        """
        session = await self.get_active_session(user_id)
        if not session:
            return None

        # Decrypt session data
        session_json = self.encryption.decrypt(
            session.encrypted_browser_state,
            session.encryption_iv
        )
        session_data = json.loads(session_json)

        # Create context with saved state - use system Chrome
        browser = await playwright_instance.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
        )

        # Restore cookies
        if session_data.get("cookies"):
            await context.add_cookies(session_data["cookies"])

        # Restore localStorage by navigating to Goldin first, then setting localStorage
        if session_data.get("localStorage"):
            page = await context.new_page()
            await page.goto("https://goldin.co", wait_until="domcontentloaded", timeout=30000)
            local_storage_data = session_data["localStorage"]
            # Use JSON to safely pass values with quotes/special chars
            for key, value in local_storage_data.items():
                await page.evaluate(
                    "(args) => localStorage.setItem(args.key, args.value)",
                    {"key": key, "value": value}
                )
            await page.close()

        return context, browser  # Return browser too so caller can close it
