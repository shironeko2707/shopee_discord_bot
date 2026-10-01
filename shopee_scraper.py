import os
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
import re
import json

from browser_manager import get_browser_context, scroll_page
from captcha_solver import handle_page_challenges


def scrape_product_data(html_content):
    """
    Parses the HTML content of a Shopee search page to extract product data.

    NOTE: The CSS selectors used here are based on common Shopee structures and
    may need to be updated if Shopee changes their website layout. If this script
    does not find any products, you will need to inspect the 'shopee_page_source.html'
    file and update the selectors in the 'product_selectors' dictionary below.
    """
    print("Starting to scrape product data...")
    soup = BeautifulSoup(html_content, 'html.parser')

    # --- SELECTORS ---
    # These selectors are updated to work with current Shopee structure
    # The structure might change, so you may need to update them.
    product_selectors = {
        "product_container": '[data-sqe="item"], .col-xs-2-4, .shopee-search-item-result__item',
        "product_link_and_name": 'a',
        "name": ".line-clamp-2, [data-sqe='name'], .shopee-search-item-result__item-name",
        "price": '[data-sqe="price"], .truncate.flex.items-baseline, .shopee-search-item-result__item-price',
        "shopee_mall_tick": 'img[alt*="Mall"], img[title*="Mall"], .shopee-mall, [class*="Mall"], [data-test*="mall"], svg[class*="mall"]',
        "favourite_tick": '[data-sqe="favourite"], [data-preferred="true"], img[alt*="yêu"], img[alt*="favourite"], img[alt*="heart"], .favourite, .preferred, .heart, [class*="favourite"], [class*="preferred"], [class*="heart"]',
        "discount": '[data-sqe="discount"], .discount, [class*="discount"], [class*="sale"], .shopee-item-card__discount, .item-card-discount, .percent, .off, [class*="percent"], [class*="off"], .sale-tag, .discount-tag, .promotion-price, [data-test*="discount"], .price-discount, .voucher-price, .flash-sale-price'
    }
    # --- END OF SELECTORS ---

    products = []

    # Try each selector one by one and see which one works
    for selector_name, selector in product_selectors.items():
        if selector_name == "product_container":
            continue
        elements = soup.select(selector)
        print(f"Selector '{selector_name}' ({selector}): found {len(elements)} elements")

        # Show what the mall elements actually are
        if selector_name == "shopee_mall_tick" and elements:
            print(f"Mall elements found:")
            for i, element in enumerate(elements):
                print(f"  {i+1}. {element}")
                parent = element.parent
                if parent:
                    print(f"     Parent: {parent.name} with classes {parent.get('class', [])}")
                print(f"     HTML: {str(element)[:200]}...")
                print()

        # Show what discount elements are found
        if selector_name == "discount" and elements:
            print(f"Discount elements found:")
            for i, element in enumerate(elements):
                print(f"  {i+1}. Text: '{element.get_text().strip()}'")
                print(f"     HTML: {str(element)[:200]}...")
                print()

    product_elements = soup.select(product_selectors["product_container"])
    print(f"Found {len(product_elements)} product elements.")

    # Debug: show the first few product elements
    if product_elements:
        print(f"\nFirst product element structure:")
        print(f"Classes: {product_elements[0].get('class', [])}")
        print(f"HTML snippet: {str(product_elements[0])[:500]}...")
        print(f"All children: {[child.name for child in product_elements[0].children if child.name]}")
    else:
        print("No product elements found!")

    for item in product_elements:
        try:
            name = None
            price = None
            url = None
            is_mall = False
            is_favourite = False
            discount = 0

            # Check for Shopee Mall tick
            mall_element = item.select_one(product_selectors["shopee_mall_tick"])
            if mall_element:
                is_mall = True
                print(f"Found mall badge: {mall_element}")

            # Also check for text content that might indicate mall
            item_text = item.get_text().lower()
            if "mall" in item_text or "shopee mall" in item_text:
                is_mall = True
                print(f"Found mall text indicator in product")

            # Check for Favourite tick
            favourite_element = item.select_one(product_selectors["favourite_tick"])
            if favourite_element:
                is_favourite = True
                print(f"Found favourite badge: {favourite_element}")

            # Also check for text content that might indicate favourite
            if "yêu thích" in item_text or "favourite" in item_text:
                is_favourite = True
                print(f"Found favourite text indicator in product")

            # Extract URL and Name
            link_element = item.select_one(product_selectors["product_link_and_name"])
            if link_element:
                url = "https://shopee.vn" + link_element['href']
                name_element = link_element.select_one(product_selectors["name"])
                if name_element:
                    name = name_element.text.strip()

            # Extract Price
            price_element = item.select_one(product_selectors["price"])
            if price_element:
                # Prices can be in formats like "₫15.000 - ₫20.000" or just "₫15.000"
                # We'll take the first number we find.
                price_text = price_element.text.replace('₫', '').replace('.', '').strip()
                price_match = re.search(r'\d+', price_text)
                if price_match:
                    price = int(price_match.group(0))

            # Extract Discount
            discount_element = item.select_one(product_selectors["discount"])
            if discount_element:
                discount_text = discount_element.text.strip().replace('%', '').replace('-', '').replace('off', '').replace('OFF', '').strip()
                # Try to extract percentage from text like "20%", "-20%", "20% off", etc.
                discount_match = re.search(r'(\d+)', discount_text)
                if discount_match:
                    try:
                        discount = int(discount_match.group(1))
                    except ValueError:
                        discount = 0
                else:
                    discount = 0
            else:
                # Try to find discount in the full item text
                item_text = item.get_text()
                discount_match = re.search(r'(\d+)%\s*(?:off|giảm|sale)', item_text, re.IGNORECASE)
                if discount_match:
                    try:
                        discount = int(discount_match.group(1))
                        print(f"Found discount in text: {discount}%")
                    except ValueError:
                        discount = 0
                else:
                    discount = 0

            if name and price and url:
                product_data = {
                    "name": name,
                    "price": price,
                    "url": url,
                    "is_mall": is_mall,
                    "is_favourite": is_favourite,
                    "discount": discount
                }
                products.append(product_data)
                print(f"Added product: {name[:50]}... - Mall: {is_mall}, Favourite: {is_favourite}")
        except Exception as e:
            print(f"Error parsing a product item: {e}")

    print(f"Successfully scraped {len(products)} products.")
    return products

def get_best_price_products(products, key, num_products=10):
    """
    Filters for products of a certain type (e.g., 'is_mall', 'is_favourite'),
    sorts them by the highest price with greatest discount, and returns the top N products.
    """
    if not products:
        return []

    # Filter for products of the specified type
    filtered_products = [p for p in products if p.get(key)]
    print(f"Found {len(filtered_products)} products for key '{key}'.")

    # Sort by discount first (highest discount first), then by price (highest price first)
    # This gives us highest priced items with the best discounts
    sorted_products = sorted(filtered_products, key=lambda x: (x.get('discount', 0), x.get('price', 0)), reverse=True)

    # Return the top `num_products`
    return sorted_products[:num_products]

def get_best_deals_from_all(products, num_products=10):
    """
    Gets the best deals from all products based on highest price with greatest discount.
    """
    if not products:
        return []

    print(f"Getting best deals from {len(products)} total products.")

    # Sort by discount first (highest discount first), then by price (highest price first)
    # This gives us highest priced items with the best discounts
    sorted_products = sorted(products, key=lambda x: (x.get('discount', 0), x.get('price', 0)), reverse=True)

    # Return the top `num_products`
    return sorted_products[:num_products]


async def run_scraper(product_name, wait_time=120):
    """
    Launches a Playwright browser, handles captchas, saves the page source,
    and scrapes the data.
    """
    page_source = None

    try:
        async with get_browser_context() as (context, page):
            search_url = f"https://shopee.vn/search?keyword={urllib.parse.quote(product_name)}"
            print(f"\nNavigating to: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)

            # Smart waiting replaces time.sleep(wait_time)
            print("Handling page challenges (captcha/login detection)...")
            status = await handle_page_challenges(page, max_wait=wait_time)
            print(f"Page challenge status: {status}")

            # Scroll to load products
            print("Scrolling to load more products...")
            await scroll_page(page)

            page_source = await page.content()
            with open("shopee_page_source.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            print("Page source saved to shopee_page_source.html")

    except Exception as e:
        print(f"Browser error: {repr(e)}")

    if page_source:
        all_products = scrape_product_data(page_source)

        if all_products:
            top_mall_products = get_best_price_products(all_products, key='is_mall', num_products=10)
            top_favourite_products = get_best_price_products(all_products, key='is_favourite', num_products=10)

            # If no mall or favourite products found, get best deals from all products
            if not top_mall_products:
                print("No mall products found, getting best deals from all products for mall category...")
                top_mall_products = get_best_deals_from_all(all_products, num_products=10)

            if not top_favourite_products:
                print("No favourite products found, getting best deals from all products for favourite category...")
                top_favourite_products = get_best_deals_from_all(all_products, num_products=10)

            results = {
                "mall": top_mall_products,
                "favourite": top_favourite_products
            }

            # Save results to a file
            with open('shopee_results.json', 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=4)
            print("\nResults saved to shopee_results.json")

        else:
            print("Could not scrape any products. Please check the HTML source and update the selectors in the script.")


async def run_multi_scraper(product_list, channel_id=None):
    """
    Scrapes multiple products sequentially.
    """
    print(f"Starting multi-search for {len(product_list)} products...")

    for i, product_name in enumerate(product_list, 1):
        print(f"\n{'='*60}")
        print(f"SEARCHING PRODUCT {i}/{len(product_list)}: {product_name}")
        print(f"{'='*60}")

        try:
            await run_scraper(product_name, wait_time=90)

            # Save results with product name prefix
            results_filename = f'shopee_results_{product_name.replace(" ", "_")[:20]}.json'

            # Read the current results and save with product name
            if os.path.exists('shopee_results.json'):
                with open('shopee_results.json', 'r', encoding='utf-8') as f:
                    results = json.load(f)

                with open(results_filename, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=4)

                print(f"Results saved to {results_filename}")

                # Print summary
                mall_count = len(results.get("mall", []))
                fav_count = len(results.get("favourite", []))
                print(f"Found {mall_count} mall deals and {fav_count} favourite deals for '{product_name}'")

        except Exception as e:
            print(f"Error scraping '{product_name}': {e}")
            continue

        # Brief pause between products
        if i < len(product_list):
            print(f"\nWaiting 10 seconds before next product...")
            await asyncio.sleep(10)

    print(f"\nMulti-search completed! Processed {len(product_list)} products.")


if __name__ == "__main__":
    product_to_search = "iphone 15 pro max"
    asyncio.run(run_scraper(product_to_search))
    print("\nScraping script finished.")
