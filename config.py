import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SHOPEE_USERNAME = os.getenv("SHOPEE_USERNAME")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")
DISCORD_USER_ID = os.getenv("DISCORD_USER_ID")
SHOPEE_API_TOKEN = os.getenv("SHOPEE_API_TOKEN")

# Captcha settings
CAPTCHA_AUTO_SOLVE = os.getenv("CAPTCHA_AUTO_SOLVE", "true").lower() == "true"
CAPTCHA_MAX_RETRIES = int(os.getenv("CAPTCHA_MAX_RETRIES", "3"))
CAPTCHA_MANUAL_TIMEOUT = int(os.getenv("CAPTCHA_MANUAL_TIMEOUT", "120"))

# Browser settings
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
BROWSER_PROFILE_DIR = os.getenv("BROWSER_PROFILE_DIR", "./shopee_profile_pw")

# Promo settings
PROMO_HISTORY_FILE = os.getenv("PROMO_HISTORY_FILE", "promo_history.json")
