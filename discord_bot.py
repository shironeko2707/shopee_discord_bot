import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import asyncio
from shopee_scraper import run_scraper, run_multi_scraper
from promo_scanner import scan_promos, get_recent_promos
from scheduler import start_scheduler_thread, add_scheduled_commands

# Load environment variables
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # Enable message content intent

bot = commands.Bot(command_prefix="!", intents=intents)

WISHLIST_FILE = "wishlist.json"

def load_wishlist():
    if os.path.exists(WISHLIST_FILE):
        with open(WISHLIST_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} # Return empty dict if file is empty or corrupt
    return {}

def save_wishlist(wishlist):
    with open(WISHLIST_FILE, "w") as f:
        json.dump(wishlist, f, indent=4)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

@bot.command()
async def help_shopee(ctx):
    """Show help for all Shopee bot commands."""
    embed = discord.Embed(
        title="Shopee Deal Bot Commands",
        description="Your personal Shopee deals finder!",
        color=discord.Color.orange()
    )

    embed.add_field(
        name="Basic Search",
        value="- `!search <product>` - Search for a single product\n"
              "- `!multisearch <product1>, <product2>, ...` - Search multiple products (max 10)",
        inline=False
    )

    embed.add_field(
        name="Promo Scanner",
        value="- `!promo_scan` - Scan Shopee for high-value promo codes & flash sales\n"
              "- `!promo_list` - View recently found promo codes",
        inline=False
    )

    embed.add_field(
        name="Scheduled Searches",
        value="- `!schedule_add <product>` - Add product to auto-search (12 PM & 12 AM daily)\n"
              "- `!schedule_remove <product>` - Remove product from auto-search\n"
              "- `!schedule_list` - View all scheduled products\n"
              "- `!schedule_test` - Test scheduled search immediately",
        inline=False
    )

    embed.add_field(
        name="Other Commands",
        value="- `!wishlist <item>` - Add item to your wishlist\n"
              "- `!view` - View your wishlist\n"
              "- `!ping` - Test bot connection",
        inline=False
    )

    embed.add_field(
        name="How it works",
        value="Bot auto-solves captchas and finds the top 10 best deals by highest discounts and prices. "
              "Shows both Mall and Favourite categories with discount percentages.",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command()
async def wishlist(ctx, *, item: str):
    """Adds an item to your wishlist."""
    user_id = str(ctx.author.id)
    wishlist_data = load_wishlist()

    if user_id not in wishlist_data:
        wishlist_data[user_id] = []

    if item not in wishlist_data[user_id]:
        wishlist_data[user_id].append(item)
        save_wishlist(wishlist_data)
        await ctx.send(f"Added '{item}' to your wishlist.")
    else:
        await ctx.send(f"'{item}' is already in your wishlist.")

@bot.command()
async def view(ctx):
    """Displays your current wishlist."""
    user_id = str(ctx.author.id)
    wishlist_data = load_wishlist()

    if user_id in wishlist_data and wishlist_data[user_id]:
        user_wishlist = "\n".join(wishlist_data[user_id])
        embed = discord.Embed(title=f"{ctx.author.name}'s Wishlist", description=user_wishlist, color=discord.Color.blue())
        await ctx.send(embed=embed)
    else:
        await ctx.send("Your wishlist is empty. Use `!wishlist <item>` to add something.")

@bot.command()
async def search(ctx, *, product_name: str):
    """Searches for a product on Shopee and returns the best deals."""
    await ctx.send(f"Searching for '{product_name}' on Shopee (auto-solving captchas)...")

    loop = asyncio.get_event_loop()
    try:
        def _run_scraper_sync(name):
            asyncio.run(run_scraper(name))

        await loop.run_in_executor(None, _run_scraper_sync, product_name)

        if os.path.exists('shopee_results.json'):
            with open('shopee_results.json', 'r', encoding='utf-8') as f:
                results = json.load(f)

            # --- Mall Products Embed ---
            mall_products = results.get("mall", [])
            if mall_products:
                mall_embed = discord.Embed(title=f"Top 10 Best Deals - Mall Category for '{product_name}'", color=discord.Color.red())
                for product in mall_products:
                    discount_text = f" ({product.get('discount', 0)}% off)" if product.get('discount', 0) > 0 else ""
                    mall_embed.add_field(
                        name=f"{product['name']}",
                        value=f"Price: {product.get('price', 'N/A'):,}d{discount_text} - [Link]({product.get('url', '#')})",
                        inline=False
                    )
                await ctx.send(embed=mall_embed)
            else:
                await ctx.send(f"No products found for '{product_name}'.")

            # --- Favourite Products Embed ---
            favourite_products = results.get("favourite", [])
            if favourite_products:
                fav_embed = discord.Embed(title=f"Top 10 Best Deals - Favourite Category for '{product_name}'", color=discord.Color.orange())
                for product in favourite_products:
                    discount_text = f" ({product.get('discount', 0)}% off)" if product.get('discount', 0) > 0 else ""
                    fav_embed.add_field(
                        name=f"{product['name']}",
                        value=f"Price: {product.get('price', 'N/A'):,}d{discount_text} - [Link]({product.get('url', '#')})",
                        inline=False
                    )
                await ctx.send(embed=fav_embed)
            else:
                await ctx.send(f"No products found for '{product_name}'.")

        else:
            await ctx.send("Scraping finished, but no results file was found.")

    except Exception as e:
        error_message = f"An error occurred: {type(e).__name__}. Check the console for details."
        print(f"Error during scraping: {e}")
        await ctx.send(error_message)

@bot.command()
async def multisearch(ctx, *, products: str):
    """Searches for multiple products on Shopee. Separate product names with commas."""
    product_list = [p.strip() for p in products.split(',')]
    total_products = len(product_list)

    if total_products > 10:
        await ctx.send("Maximum 10 products allowed per multi-search.")
        return

    await ctx.send(f"Starting multi-search for {total_products} products (auto-solving captchas)...")
    await ctx.send(f"Products: {', '.join(product_list)}")

    loop = asyncio.get_event_loop()
    try:
        def _run_multi_sync(pl, cid):
            asyncio.run(run_multi_scraper(pl, cid))

        await loop.run_in_executor(None, _run_multi_sync, product_list, ctx.channel.id)
        await ctx.send("Multi-search completed! Check the results above.")

    except Exception as e:
        error_message = f"An error occurred during multi-search: {type(e).__name__}. Check the console for details."
        print(f"Error during multi-search: {e}")
        await ctx.send(error_message)

@bot.command()
async def promo_scan(ctx, *, category: str = "all"):
    """Scan for high-value promo codes on Shopee. Usage: !promo_scan [all|electronics]"""
    await ctx.send(f"Scanning Shopee for promos (filter: {category})...")

    loop = asyncio.get_event_loop()
    try:
        def _run_scan_sync():
            return asyncio.run(scan_promos(category_filter=category))

        promos = await loop.run_in_executor(None, _run_scan_sync)

        if promos:
            # Split into vouchers and product deals
            vouchers = [p for p in promos if p["type"] == "platform"]
            deals = [p for p in promos if p["type"] == "product_deal"]

            # Voucher embed
            if vouchers:
                v_embed = discord.Embed(
                    title=f"Voucher Codes ({len(vouchers)} found)",
                    color=discord.Color.green()
                )
                for v in vouchers[:10]:
                    discount_str = f"Giam {v['discount_percent']}%" if v.get("discount_percent") else ""
                    max_str = f" (max {v['max_discount']//1000}k)" if v.get("max_discount") else ""
                    min_str = f" | Min: {v['min_spend']//1000}k" if v.get("min_spend") else ""
                    status_str = f" | {v['status']}" if v.get("status") else ""
                    v_embed.add_field(
                        name=f"{discount_str}{max_str}",
                        value=f"{min_str}{status_str}".strip(" |") or "Platform voucher",
                        inline=False
                    )
                await ctx.send(embed=v_embed)

            # Product deals embed
            if deals:
                d_embed = discord.Embed(
                    title=f"Top Product Deals ({len(deals)} found)",
                    color=discord.Color.red()
                )
                for d in deals[:15]:
                    name = (d.get("name") or "Unknown")[:60]
                    price_str = f" - {d['price']:,}d" if d.get("price") else ""
                    url = d.get("url", "#")
                    d_embed.add_field(
                        name=f"-{d['discount_percent']}% | {name}",
                        value=f"Price: {price_str} - [Link]({url})" if d.get("url") else f"Price:{price_str}",
                        inline=False
                    )
                await ctx.send(embed=d_embed)

            if not vouchers and not deals:
                await ctx.send("No promos found matching the filter.")
        else:
            await ctx.send("No promos found. Shopee's layout may have changed - check debug HTML files.")

    except Exception as e:
        error_message = f"Promo scan error: {type(e).__name__}. Check the console for details."
        print(f"Error during promo scan: {e}")
        await ctx.send(error_message)

@bot.command()
async def promo_list(ctx):
    """View recently found promo codes."""
    promos = get_recent_promos(limit=15)

    if promos:
        embed = discord.Embed(
            title="Recent Shopee Promos",
            description=f"Showing {len(promos)} most recent promos",
            color=discord.Color.gold()
        )

        for promo in promos:
            discount_str = ""
            if promo.get("discount_percent"):
                discount_str = f"{promo['discount_percent']}% off"
            if promo.get("discount_amount"):
                if discount_str:
                    discount_str += f" / {promo['discount_amount']:,}d"
                else:
                    discount_str = f"{promo['discount_amount']:,}d off"

            found_at = promo.get("found_at", "unknown")[:16]
            code_str = f" | Code: `{promo['code']}`" if promo.get("code") else ""

            embed.add_field(
                name=f"[{promo['type'].upper()}] {discount_str}",
                value=f"Category: {promo.get('category', 'General')}{code_str} | Found: {found_at}",
                inline=False
            )

        await ctx.send(embed=embed)
    else:
        await ctx.send("No promo history found. Run `!promo_scan` first to scan for promos.")

def run_bot():
    if DISCORD_BOT_TOKEN:
        # Add scheduler commands to the bot
        add_scheduled_commands(bot)

        # Start the scheduler in background
        print("Starting scheduler...")
        start_scheduler_thread()

        # Start the bot
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("Discord bot token not found. Please set it in the .env file.")
