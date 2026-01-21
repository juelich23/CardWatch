"""
Fanatics Collect authentication via browser automation

NOTE: This is a skeleton implementation that follows the Goldin pattern.
Fanatics uses FanID (a unified SSO system) which may require additional
testing and refinement with real credentials.

The login flow needs to be verified:
1. Navigate to login page
2. Enter email/password (may be separate steps like Goldin)
3. Handle any 2FA or verification
4. Extract session cookies for authenticated API calls
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


class FanaticsAuthService:
    """Handle Fanatics Collect authentication via browser automation"""

    # Fanatics login URLs - may redirect to FanID
    LOGIN_URL = "https://www.fanaticscollect.com/login"
    ACCOUNT_URL = "https://www.fanaticscollect.com/account"
    WEEKLY_URL = "https://www.fanaticscollect.com/weekly"
    SESSION_DURATION = timedelta(hours=12)

    def __init__(self, db: AsyncSession):
        self.db = db
        self.credential_manager = CredentialManager(db)
        self.encryption = get_encryption_service()

    async def login(self, user_id: int) -> Tuple[bool, str]:
        """
        Perform Fanatics login for a user.

        NOTE: Fanatics has strong anti-bot protection on their login system.
        Automated login is currently not fully supported. This is a best-effort
        implementation that may require manual intervention.

        Returns:
            tuple of (success: bool, message: str)
        """
        # Get user's Fanatics credentials
        credential = await self.credential_manager.get_credential(user_id, "fanatics")
        if not credential:
            return False, "No Fanatics credentials stored for this user"

        username, password = self.credential_manager.decrypt_credentials(credential)

        browser = None
        p = None
        try:
            p = await async_playwright().start()
            # Use Firefox as it has better compatibility with Fanatics
            browser = await p.firefox.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
                viewport={'width': 1920, 'height': 1080},
            )
            page = await context.new_page()

            # Navigate to Fanatics Collect main page
            print(f"   Navigating to Fanatics Collect...")
            await page.goto("https://www.fanaticscollect.com/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)

            # Click LOG IN button
            print(f"   Looking for LOG IN button...")
            login_btn = await page.query_selector('button:has-text("LOG IN")')
            if not login_btn:
                return False, "Could not find LOG IN button on Fanatics Collect"

            # Track new pages/popups
            new_pages = []
            context.on("page", lambda p: new_pages.append(p))

            await login_btn.click()
            await asyncio.sleep(5)

            # Check if a popup opened
            target_page = page
            if new_pages:
                target_page = new_pages[-1]
                print(f"   Login popup opened: {target_page.url}")
                await asyncio.sleep(3)

            # Look for email input in target page
            email_input = None
            for selector in [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email"]',
                'input[autocomplete="email"]',
                'input[placeholder*="email" i]',
            ]:
                email_input = await target_page.query_selector(selector)
                if email_input:
                    try:
                        is_visible = await email_input.is_visible()
                        if is_visible:
                            print(f"   Found email input: {selector}")
                            break
                    except:
                        pass
                    email_input = None

            if not email_input:
                # Wait for dynamic content
                try:
                    email_input = await target_page.wait_for_selector(
                        'input[type="email"], input[name="email"]',
                        timeout=10000
                    )
                except:
                    pass

            if not email_input:
                # Fanatics has anti-bot protection that blocks automated login
                return False, "Fanatics login blocked - anti-bot protection detected. Manual login required via browser."

            # Enter credentials
            await email_input.fill(username)
            await asyncio.sleep(1)

            # Find and click continue/submit
            continue_btn = await target_page.query_selector(
                'button[type="submit"], button:has-text("Continue"), button:has-text("Next"), button:has-text("Sign In")'
            )
            if continue_btn:
                await continue_btn.click()
                await asyncio.sleep(3)

            # Look for password field
            password_input = await target_page.query_selector('input[type="password"]')
            if not password_input:
                try:
                    password_input = await target_page.wait_for_selector('input[type="password"]', timeout=10000)
                except:
                    return False, "Could not find password field"

            await password_input.fill(password)
            await asyncio.sleep(1)

            # Submit
            submit_btn = await target_page.query_selector(
                'button[type="submit"], button:has-text("Sign In"), button:has-text("Log In")'
            )
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(5)

            # Check for login success
            await page.reload(wait_until="networkidle")
            await asyncio.sleep(3)

            # Verify login state
            login_btn_still_there = await page.query_selector('button:has-text("LOG IN")')
            if login_btn_still_there:
                return False, "Login failed. Please verify your Fanatics credentials."

            # Success - save session
            session_data = await self._extract_session_data(context, page)
            await self._save_session(user_id, credential.id, session_data)

            credential.is_valid = True
            credential.last_verified = datetime.utcnow()
            credential.last_error = None
            await self.db.commit()

            print(f"   Fanatics login successful!")
            return True, "Successfully logged in to Fanatics Collect"

        except Exception as e:
            error_msg = str(e)
            print(f"   Fanatics login error: {error_msg}")

            # Provide helpful message for anti-bot issues
            if "closed" in error_msg.lower() or "target" in error_msg.lower():
                return False, "Fanatics login blocked by anti-bot protection. Manual login may be required."

            if credential:
                await self.credential_manager.mark_credential_invalid(credential, error_msg)
            return False, f"Login error: {error_msg}"

        finally:
            if browser:
                await browser.close()
            if p:
                await p.stop()

    async def _extract_session_data(self, context: BrowserContext, page) -> dict:
        """Extract cookies and localStorage for session persistence"""
        cookies = await context.cookies()

        # Get localStorage
        local_storage = await page.evaluate("""() => {
            const items = {};
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                items[key] = localStorage.getItem(key);
            }
            return items;
        }""")

        return {
            "cookies": cookies,
            "localStorage": local_storage,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _save_session(self, user_id: int, credential_id: int, session_data: dict):
        """Save encrypted session to database"""
        session_json = json.dumps(session_data)
        encrypted_session, iv = self.encryption.encrypt(session_json)

        # Deactivate existing sessions
        existing_query = select(UserSession).where(
            UserSession.credential_id == credential_id,
            UserSession.is_active == True
        )
        result = await self.db.execute(existing_query)
        for session in result.scalars().all():
            session.is_active = False

        # Create new session
        new_session = UserSession(
            credential_id=credential_id,
            encrypted_browser_state=encrypted_session,
            encryption_iv=iv,
            expires_at=datetime.utcnow() + self.SESSION_DURATION,
            is_active=True
        )
        self.db.add(new_session)
        await self.db.commit()

    async def get_active_session(self, user_id: int) -> Optional[UserSession]:
        """Get active session for user"""
        credential = await self.credential_manager.get_credential(user_id, "fanatics")
        if not credential:
            return None

        query = select(UserSession).where(
            UserSession.credential_id == credential.id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
