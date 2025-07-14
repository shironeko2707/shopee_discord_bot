import time
from discord_bot import run_bot
from shopee_scraper import run_scraper

def main():
    """
    Main function of the application.
    """
    print("Starting the Discord bot...")
    run_bot()

if __name__ == "__main__":
    main()
