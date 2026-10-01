import asyncio
import os
from pathlib import Path
from config import CAPTCHA_AUTO_SOLVE, CAPTCHA_MAX_RETRIES, CAPTCHA_MANUAL_TIMEOUT, DISCORD_USER_ID

CAPTCHA_TMP_DIR = Path("./captcha_tmp")
CAPTCHA_TMP_DIR.mkdir(exist_ok=True)

# Product container selectors (same as shopee_scraper.py)
SEARCH_RESULT_SELECTORS = [
    '[data-sqe="item"]',
    '.col-xs-2-4',
    '.shopee-search-item-result__item',
]


async def detect_captcha(page):
    """Check if an HCaptcha challenge is present on the page."""
    captcha_selectors = [
        'iframe[src*="hcaptcha.com"]',
        'div.h-captcha',
        'iframe[title*="hCaptcha"]',
        'iframe[src*="newassets.hcaptcha.com"]',
    ]
    for selector in captcha_selectors:
        element = await page.query_selector(selector)
        if element:
            return True
    return False


async def detect_login_page(page):
    """Check if the page is a login/authentication page."""
    url = page.url.lower()
    if "buyer/login" in url or "auth" in url or "signin" in url:
        return True
    login_selectors = [
        'input[name="loginKey"]',
        'input[name="password"]',
        'form[action*="login"]',
        '[class*="login-form"]',
    ]
    for selector in login_selectors:
        element = await page.query_selector(selector)
        if element:
            return True
    return False


async def detect_search_results(page):
    """Check if search results are visible on the page."""
    for selector in SEARCH_RESULT_SELECTORS:
        elements = await page.query_selector_all(selector)
        if len(elements) >= 3:
            return True
    return False


async def attempt_auto_solve(page, max_retries=None):
    """
    Attempt to solve HCaptcha automatically using hcaptcha-challenger.
    Returns True if solved, False if failed.
    """
    if max_retries is None:
        max_retries = CAPTCHA_MAX_RETRIES

    try:
        import hcaptcha_challenger as solver
        from hcaptcha_challenger.agents import AgentT

        solver.install(upgrade=True)
    except ImportError:
        print("hcaptcha-challenger not installed. Cannot auto-solve.")
        return False

    for attempt in range(1, max_retries + 1):
        print(f"Captcha solve attempt {attempt}/{max_retries}...")
        try:
            agent = AgentT.from_page(page=page, tmp_dir=str(CAPTCHA_TMP_DIR))
            await agent.handle_checkbox()
            result = await agent.execute()

            if result and result.success:
                print(f"Captcha solved on attempt {attempt}!")
                return True

            # Check if captcha is still present
            await asyncio.sleep(2)
            if not await detect_captcha(page):
                print("Captcha no longer detected - likely solved!")
                return True

            print(f"Attempt {attempt} failed, retrying...")
            await asyncio.sleep(2)

        except Exception as e:
            print(f"Captcha solve attempt {attempt} error: {e}")
            await asyncio.sleep(2)

    print("All auto-solve attempts exhausted.")
    return False


async def notify_manual_captcha(bot):
    """Send a Discord DM to the bot owner requesting manual captcha solving."""
    if not DISCORD_USER_ID or not bot:
        print("Cannot notify: DISCORD_USER_ID not set or bot not provided.")
        return

    try:
        user = await bot.fetch_user(int(DISCORD_USER_ID))
        if user:
            await user.send(
                "Manual captcha solving needed! "
                "Please open the browser window and solve the captcha. "
                "The bot will continue automatically once the captcha is cleared."
            )
            print(f"Sent manual captcha notification to user {DISCORD_USER_ID}")
    except Exception as e:
        print(f"Failed to send captcha notification: {e}")


async def handle_page_challenges(page, max_wait=120, bot=None):
    """
    Main handler that replaces the old time.sleep(wait_time).
    Handles captcha, login detection, and waits for search results.

    Returns: "ready", "login_required", or "timeout"
    """
    # Initial wait for page to settle
    await asyncio.sleep(3)

    elapsed = 0
    poll_interval = 5

    while elapsed < max_wait:
        # Check for captcha
        if await detect_captcha(page):
            print("Captcha detected!")
            if CAPTCHA_AUTO_SOLVE:
                solved = await attempt_auto_solve(page)
                if solved:
                    await asyncio.sleep(3)
                    continue
                else:
                    # Auto-solve failed, notify user
                    await notify_manual_captcha(bot)
                    print("Waiting for manual captcha solve...")
            else:
                await notify_manual_captcha(bot)
                print("Auto-solve disabled. Waiting for manual captcha solve...")

            # Poll until captcha disappears
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                if not await detect_captcha(page):
                    print("Captcha cleared!")
                    break
            else:
                return "timeout"
            await asyncio.sleep(2)
            continue

        # Check for login page
        if await detect_login_page(page):
            print("Login page detected. Waiting for user to log in...")
            await notify_manual_captcha(bot)
            while elapsed < max_wait:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
                if not await detect_login_page(page):
                    print("Login completed!")
                    break
            else:
                return "login_required"
            await asyncio.sleep(3)
            continue

        # Check for search results
        if await detect_search_results(page):
            print("Search results detected! Page is ready.")
            return "ready"

        # Nothing found yet, keep waiting
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    # Final check before timeout
    if await detect_search_results(page):
        return "ready"

    print(f"Timed out after {max_wait}s waiting for page to be ready.")
    return "timeout"
