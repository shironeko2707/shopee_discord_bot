import subprocess
import sys
from discord_bot import run_bot


def check_playwright_browsers():
    """Check if Playwright browsers are installed, install if needed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Try to get the executable path - will fail if not installed
            p.chromium.executable_path
        print("Playwright Chromium browser found.")
    except Exception:
        print("Playwright browsers not found. Installing Chromium...")
        try:
            subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
            print("Playwright Chromium installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install Playwright browsers: {e}")
            print("Please run manually: playwright install chromium")
            sys.exit(1)


def main():
    """
    Main function of the application.
    """
    print("Checking Playwright browser installation...")
    check_playwright_browsers()

    print("Starting the Discord bot...")
    run_bot()

if __name__ == "__main__":
    main()
