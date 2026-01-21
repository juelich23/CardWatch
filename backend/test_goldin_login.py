#!/usr/bin/env python3
"""Debug script to test Goldin login with Playwright"""
import asyncio
from playwright.async_api import async_playwright

async def test_goldin_login():
    print("Starting Playwright...")

    p = await async_playwright().start()
    browser = await p.chromium.launch(headless=True, channel="chrome")
    context = await browser.new_context(
        user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        viewport={'width': 1920, 'height': 1080},
    )
    page = await context.new_page()

    try:
        print("Navigating to Goldin signIn page...")
        await page.goto("https://goldin.co/signIn", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Step 1: Enter email
        email_input = await page.query_selector('input[type="email"]')
        if email_input:
            print("Found email input, filling it...")
            await email_input.fill("test@example.com")
            await asyncio.sleep(1)

            # Click Continue
            continue_btn = await page.query_selector('button:has-text("Continue")')
            if continue_btn:
                print("Clicking Continue...")
                await continue_btn.click()
                await asyncio.sleep(3)

                # Step 2: Check what we have now
                print("\n=== After clicking Continue ===")
                print(f"Current URL: {page.url}")

                # Check for password input
                password_input = await page.query_selector('input[type="password"]')
                print(f"Password input found: {password_input is not None}")

                if password_input:
                    await password_input.fill("testpassword123")
                    await asyncio.sleep(1)

                # List all buttons
                print("\nAll buttons after password step:")
                all_buttons = await page.query_selector_all('button')
                for i, btn in enumerate(all_buttons):
                    try:
                        btn_text = await btn.inner_text()
                        btn_type = await btn.get_attribute('type')
                        btn_class = await btn.get_attribute('class')
                        is_visible = await btn.is_visible()
                        print(f"  {i}: type={btn_type}, visible={is_visible}, class={btn_class[:50] if btn_class else 'N/A'}, text='{btn_text.strip()[:30]}'")
                    except Exception as e:
                        print(f"  {i}: Error - {e}")

                # Try different selectors for submit button
                print("\nTrying different submit button selectors:")
                selectors = [
                    'button:has-text("Sign In")',
                    'button:has-text("Log In")',
                    'button:has-text("Login")',
                    'button:has-text("Submit")',
                    'button[type="submit"]',
                    'form button',
                    'button:has-text("Continue")',  # Maybe Continue again?
                ]
                for sel in selectors:
                    btn = await page.query_selector(sel)
                    print(f"  {sel}: {btn is not None}")

        print("\nTest completed!")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()
        await p.stop()
        print("Done")

if __name__ == "__main__":
    asyncio.run(test_goldin_login())
