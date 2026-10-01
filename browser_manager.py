import asyncio
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
from config import BROWSER_HEADLESS, BROWSER_PROFILE_DIR


@asynccontextmanager
async def get_browser_context():
    """
    Async context manager that provides a persistent Playwright browser context.
    Yields (browser, context, page) tuple.
    """
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=BROWSER_PROFILE_DIR,
            headless=BROWSER_HEADLESS,
            viewport={"width": 1920, "height": 1080},
            locale="vi-VN",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--start-maximized",
            ],
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            yield context, page
        finally:
            await context.close()


async def scroll_page(page, scroll_count=4, delay_ms=3000):
    """Scroll page multiple times to load lazy-loaded content."""
    for i in range(scroll_count):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(delay_ms / 1000)
    # Scroll back to top then bottom once more
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    await asyncio.sleep(delay_ms / 1000)
