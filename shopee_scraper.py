import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import urllib.parse
from bs4 import BeautifulSoup
import re
import json

# Load environment variables
load_dotenv()

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


def run_scraper(product_name, wait_time=120):
    """
    Launches a browser, saves the page source, and then scrapes the data.
    wait_time: Time to wait in seconds (default 120 = 2 minutes)
    """
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--user-data-dir=./shopee_profile')
    options.add_argument('--disable-automation')
    options.add_argument('--start-maximized')

    driver = uc.Chrome(options=options)
    page_source = None

    try:
        search_url = f"https://shopee.vn/search?keyword={urllib.parse.quote(product_name)}"
        driver.get(search_url)
        
        print("\n" + "="*50)
        print("ACTION REQUIRED")
        print("A browser window has been opened. Please follow these steps:")
        print("1. Log in to your Shopee account if prompted.")
        print("2. Solve any CAPTCHAs that appear.")
        print("3. Scroll down the page several times to load more products.")
        print("4. Ensure the search results for '{}' are visible.".format(product_name))
        print("5. Look for products with 'Yêu Thích' badges if available.")
        print(f"\nThe script will wait for {wait_time/60:.1f} minutes for you to complete these actions.")
        print("="*50 + "\n")

        time.sleep(wait_time)
        
        # Additional scroll to ensure products are loaded
        print("Scrolling to load more products...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(5)

        print("Timer finished. Getting page source...")
        page_source = driver.page_source
        
        with open("shopee_page_source.html", "w", encoding="utf-8") as f:
            f.write(page_source)
        print("Page source saved to shopee_page_source.html")

    except Exception as e:
        print(f"An error occurred while driving the browser: {repr(e)}")
        driver.save_screenshot('shopee_error.png')
    finally:
        driver.quit()

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


def run_multi_scraper(product_list, channel_id=None):
    """
    Scrapes multiple products sequentially, each for 1.5 minutes.
    """
    print(f"Starting multi-search for {len(product_list)} products...")
    
    for i, product_name in enumerate(product_list, 1):
        print(f"\n{'='*60}")
        print(f"SEARCHING PRODUCT {i}/{len(product_list)}: {product_name}")
        print(f"{'='*60}")
        
        try:
            # Run scraper for 1.5 minutes (90 seconds)
            run_scraper(product_name, wait_time=90)
            
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
            time.sleep(10)
    
    print(f"\n🎉 Multi-search completed! Processed {len(product_list)} products.")

if __name__ == "__main__":
    # You can change the product name here
    product_to_search = "iphone 15 pro max" 
    run_scraper(product_to_search)
    print("\nScraping script finished.")