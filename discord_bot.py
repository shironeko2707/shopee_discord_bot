import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import asyncio
from shopee_scraper import run_scraper, run_multi_scraper
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
        title="🛒 Shopee Deal Bot Commands", 
        description="Your personal Shopee deals finder!",
        color=discord.Color.orange()
    )
    
    embed.add_field(
        name="🔍 Basic Search",
        value="• `!search <product>` - Search for a single product (2 min scan)\n"
              "• `!multisearch <product1>, <product2>, ...` - Search multiple products (1.5 min each, max 10)",
        inline=False
    )
    
    embed.add_field(
        name="📅 Scheduled Searches",
        value="• `!schedule_add <product>` - Add product to auto-search (12 PM & 12 AM daily)\n"
              "• `!schedule_remove <product>` - Remove product from auto-search\n"
              "• `!schedule_list` - View all scheduled products\n"
              "• `!schedule_test` - Test scheduled search immediately",
        inline=False
    )
    
    embed.add_field(
        name="📋 Other Commands",
        value="• `!wishlist <item>` - Add item to your wishlist\n"
              "• `!view` - View your wishlist\n"
              "• `!ping` - Test bot connection",
        inline=False
    )
    
    embed.add_field(
        name="ℹ️ How it works",
        value="Bot finds the top 10 best deals by highest discounts and prices. "
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
    await ctx.send(f"Starting the search for '{product_name}'. This will take a few minutes...")
    
    loop = asyncio.get_event_loop()
    try:
        # Run the synchronous scraper function in a separate thread
        await loop.run_in_executor(None, run_scraper, product_name)
        
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
                        value=f"Price: ₫{product.get('price', 'N/A'):,}{discount_text} - [Link]({product.get('url', '#')})",
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
                        value=f"Price: ₫{product.get('price', 'N/A'):,}{discount_text} - [Link]({product.get('url', '#')})",
                        inline=False
                    )
                await ctx.send(embed=fav_embed)
            else:
                await ctx.send(f"No products found for '{product_name}'.")

        else:
            await ctx.send("Scraping finished, but no results file was found.")

    except Exception as e:
        # Send a shorter, more user-friendly error message
        error_message = f"An error occurred: {type(e).__name__}. Check the console for details."
        print(f"Error during scraping: {e}") # Print full error to console
        await ctx.send(error_message)

@bot.command()
async def multisearch(ctx, *, products: str):
    """Searches for multiple products on Shopee. Separate product names with commas."""
    product_list = [p.strip() for p in products.split(',')]
    total_products = len(product_list)
    
    if total_products > 10:
        await ctx.send("Maximum 10 products allowed per multi-search.")
        return
    
    await ctx.send(f"Starting multi-search for {total_products} products. Each product takes 1.5 minutes...")
    await ctx.send(f"Products: {', '.join(product_list)}")
    await ctx.send(f"Estimated total time: {total_products * 1.5:.1f} minutes")
    
    loop = asyncio.get_event_loop()
    try:
        # Run the multi-scraper function in a separate thread
        await loop.run_in_executor(None, run_multi_scraper, product_list, ctx.channel.id)
        
        # After completion, send a completion message
        await ctx.send("🎉 Multi-search completed! Check the results above.")
        
    except Exception as e:
        error_message = f"An error occurred during multi-search: {type(e).__name__}. Check the console for details."
        print(f"Error during multi-search: {e}")
        await ctx.send(error_message)

def run_bot():
    if DISCORD_BOT_TOKEN:
        # Add scheduler commands to the bot
        add_scheduled_commands(bot)
        
        # Start the scheduler in background
        print("🚀 Starting scheduler...")
        start_scheduler_thread()
        
        # Start the bot
        bot.run(DISCORD_BOT_TOKEN)
    else:
        print("Discord bot token not found. Please set it in the .env file.")