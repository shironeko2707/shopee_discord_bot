import schedule
import time
import threading
import json
import os
from datetime import datetime
from shopee_scraper import run_scraper
from discord_bot import bot
import asyncio
import discord

# Configuration
SCHEDULE_CONFIG_FILE = "schedule_config.json"
DEFAULT_PRODUCTS = ["iphone 15 pro max", "macbook pro m4", "samsung galaxy s24"]

def load_schedule_config():
    """Load scheduled products from config file."""
    if os.path.exists(SCHEDULE_CONFIG_FILE):
        with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"products": DEFAULT_PRODUCTS, "channel_id": None}
    return {"products": DEFAULT_PRODUCTS, "channel_id": None}

def save_schedule_config(config):
    """Save scheduled products to config file."""
    with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def scheduled_search():
    """Run scheduled search for configured products."""
    print(f"\n🕒 Starting scheduled search at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = load_schedule_config()
    products = config.get("products", DEFAULT_PRODUCTS)
    
    print(f"Scheduled products: {products}")
    
    for i, product in enumerate(products, 1):
        print(f"\n📱 Scheduled search {i}/{len(products)}: {product}")
        try:
            # Run scraper for 1.5 minutes for scheduled searches
            run_scraper(product, wait_time=90)
            
            # Save results with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            results_filename = f'scheduled_{timestamp}_{product.replace(" ", "_")[:15]}.json'
            
            if os.path.exists('shopee_results.json'):
                with open('shopee_results.json', 'r', encoding='utf-8') as f:
                    results = json.load(f)
                
                with open(results_filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)
                
                print(f"✅ Scheduled results saved to {results_filename}")
                
                # Summary
                mall_count = len(results.get("mall", []))
                fav_count = len(results.get("favourite", []))
                print(f"📊 Found {mall_count} mall deals and {fav_count} favourite deals")
                
        except Exception as e:
            print(f"❌ Error in scheduled search for '{product}': {e}")
            continue
        
        # Brief pause between products in scheduled search
        if i < len(products):
            print("⏳ Waiting 30 seconds before next product...")
            time.sleep(30)
    
    print(f"🎉 Scheduled search completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

def start_scheduler():
    """Start the scheduler in a separate thread."""
    # Schedule searches at 12:00 PM and 12:00 AM
    schedule.every().day.at("12:00").do(scheduled_search)  # 12 PM
    schedule.every().day.at("00:00").do(scheduled_search)  # 12 AM
    
    print("📅 Scheduler started!")
    print("⏰ Scheduled searches:")
    print("   - 12:00 PM (noon) daily")
    print("   - 12:00 AM (midnight) daily")
    
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

def start_scheduler_thread():
    """Start scheduler in background thread."""
    scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    scheduler_thread.start()
    return scheduler_thread

# Add commands to manage scheduled products
def add_scheduled_commands(bot):
    """Add scheduler-related commands to the Discord bot."""
    
    @bot.command()
    async def schedule_add(ctx, *, product: str):
        """Add a product to the scheduled search list."""
        config = load_schedule_config()
        
        if product not in config["products"]:
            config["products"].append(product)
            save_schedule_config(config)
            await ctx.send(f"✅ Added '{product}' to scheduled searches.\nTotal scheduled products: {len(config['products'])}")
        else:
            await ctx.send(f"⚠️ '{product}' is already in the scheduled search list.")
    
    @bot.command()
    async def schedule_remove(ctx, *, product: str):
        """Remove a product from the scheduled search list."""
        config = load_schedule_config()
        
        if product in config["products"]:
            config["products"].remove(product)
            save_schedule_config(config)
            await ctx.send(f"✅ Removed '{product}' from scheduled searches.\nRemaining scheduled products: {len(config['products'])}")
        else:
            await ctx.send(f"⚠️ '{product}' is not in the scheduled search list.")
    
    @bot.command()
    async def schedule_list(ctx):
        """List all scheduled products."""
        config = load_schedule_config()
        products = config["products"]
        
        if products:
            embed = discord.Embed(title="📅 Scheduled Products", color=discord.Color.blue())
            embed.add_field(
                name="Products (searched at 12 PM & 12 AM daily)",
                value="\n".join([f"• {product}" for product in products]),
                inline=False
            )
            embed.add_field(
                name="Next scheduled times",
                value="🕐 12:00 PM (noon)\n🕛 12:00 AM (midnight)",
                inline=False
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("📋 No products scheduled for automatic searches.")
    
    @bot.command()
    async def schedule_test(ctx):
        """Run a test scheduled search immediately."""
        await ctx.send("🧪 Running test scheduled search...")
        
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(None, scheduled_search)
            await ctx.send("✅ Test scheduled search completed!")
        except Exception as e:
            await ctx.send(f"❌ Test scheduled search failed: {e}")

if __name__ == "__main__":
    print("Starting scheduler...")
    start_scheduler()