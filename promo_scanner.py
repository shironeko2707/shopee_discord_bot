import asyncio
import hashlib
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup
import re

from browser_manager import get_browser_context, scroll_page
from captcha_solver import handle_page_challenges
from config import PROMO_HISTORY_FILE

# Target URLs for promo scanning
PROMO_URLS = {
    "voucher": "https://shopee.vn/m/ma-giam-gia",
    "flash_sale": "https://shopee.vn/flash_sale",
    "electronics": "https://shopee.vn/Thi%E1%BA%BFt-B%E1%BB%8B-%C4%90i%E1%BB%87n-T%E1%BB%AD-cat.11036132",
}

# CSS selectors for promo elements (updated from actual Shopee HTML structure)
VOUCHER_SELECTORS = {
    "card": 'div.bWMrf7',
    "discount_text": 'div.O3rwgP',
    "details": 'div.Zx9zTr',
    "status": 'div.h_wf5Y',
}

PRODUCT_DEAL_SELECTORS = {
    "discount_badge": 'div.bg-shopee-pink',
    "name": 'div.line-clamp-2',
    "price": 'div.truncate.flex.items-baseline',
}

FLASH_SALE_SELECTORS = {
    "item": '[class*="flash-sale"] [class*="item"], [class*="flashSale"] [class*="item"], [data-sqe="item"]',
    "price": '[class*="price"], [class*="Price"]',
    "discount": 'div.bg-shopee-pink, [class*="discount"], [class*="percent"]',
    "name": 'div.line-clamp-2, [class*="name"]',
}


def generate_promo_id(promo_data):
    """Generate a unique 12-char hash ID for a promo."""
    key = f"{promo_data.get('type', '')}{promo_data.get('discount_percent', '')}{promo_data.get('source_url', '')}{promo_data.get('category', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def load_promo_history():
    """Load promo history from JSON file."""
    if os.path.exists(PROMO_HISTORY_FILE):
        try:
            with open(PROMO_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def save_promo_history(promos):
    """Save promo history to JSON file."""
    with open(PROMO_HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(promos, f, ensure_ascii=False, indent=4)


def merge_promos(existing, new_promos):
    """Merge new promos into existing list, deduplicating by ID."""
    existing_ids = {p["id"] for p in existing}
    for promo in new_promos:
        if promo["id"] not in existing_ids:
            existing.append(promo)
            existing_ids.add(promo["id"])
    return existing


def parse_vouchers(html_content, source_url):
    """Parse voucher codes and product deals from Shopee promo page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    promos = []

    # === VOUCHER CARDS (e.g. "Giảm 25%", "Giảm tối đa 100k₫") ===
    voucher_cards = soup.select(VOUCHER_SELECTORS["card"])
    print(f"Found {len(voucher_cards)} voucher card elements")

    for card in voucher_cards:
        try:
            promo = {
                "type": "platform",
                "discount_percent": None,
                "discount_amount": None,
                "min_spend": None,
                "max_discount": None,
                "status": None,
                "expiry": None,
                "category": None,
                "code": None,
                "source_url": source_url,
                "found_at": datetime.now().isoformat(),
            }

            # Discount text: "Giảm 25%"
            discount_el = card.select_one(VOUCHER_SELECTORS["discount_text"])
            if discount_el:
                discount_text = discount_el.get_text(strip=True)
                percent_match = re.search(r'(\d+)\s*%', discount_text)
                if percent_match:
                    promo["discount_percent"] = int(percent_match.group(1))

            # Details: "Giảm tối đa 100k₫ Đơn Tối Thiểu 100k₫"
            details_el = card.select_one(VOUCHER_SELECTORS["details"])
            if details_el:
                details_text = details_el.get_text(strip=True)
                # Max discount: "Giảm tối đa 100k₫" or "300k₫"
                max_match = re.search(r'tối đa\s*(\d+)k', details_text, re.IGNORECASE)
                if max_match:
                    promo["max_discount"] = int(max_match.group(1)) * 1000
                # Min spend: "Đơn Tối Thiểu 100k₫" or "500k₫"
                min_match = re.search(r'[Tt]ối [Tt]hiểu\s*(\d+)k', details_text)
                if min_match:
                    promo["min_spend"] = int(min_match.group(1)) * 1000

            # Status: "Hết lượt sử dụng" or usage progress
            status_el = card.select_one(VOUCHER_SELECTORS["status"])
            if status_el:
                promo["status"] = status_el.get_text(strip=True)

            if promo["discount_percent"] or promo["discount_amount"]:
                promo["id"] = generate_promo_id(promo)
                promos.append(promo)

        except Exception as e:
            print(f"Error parsing voucher card: {e}")
            continue

    # === PRODUCT DEALS (items with -XX% discount badges) ===
    discount_badges = soup.select(PRODUCT_DEAL_SELECTORS["discount_badge"])
    print(f"Found {len(discount_badges)} product deal badges")

    for badge in discount_badges:
        try:
            link = badge.find_parent('a')
            if not link:
                continue

            promo = {
                "type": "product_deal",
                "discount_percent": None,
                "discount_amount": None,
                "min_spend": None,
                "name": None,
                "price": None,
                "url": None,
                "expiry": None,
                "category": None,
                "code": None,
                "source_url": source_url,
                "found_at": datetime.now().isoformat(),
            }

            # Discount: "-46%"
            badge_text = badge.get_text(strip=True)
            percent_match = re.search(r'(\d+)%', badge_text)
            if percent_match:
                promo["discount_percent"] = int(percent_match.group(1))

            # Product name
            name_el = link.select_one(PRODUCT_DEAL_SELECTORS["name"])
            if name_el:
                promo["name"] = name_el.get_text(strip=True)

            # Price
            price_el = link.select_one(PRODUCT_DEAL_SELECTORS["price"])
            if price_el:
                price_text = price_el.get_text(strip=True).replace('₫', '').replace('.', '').strip()
                price_match = re.search(r'(\d+)', price_text)
                if price_match:
                    promo["price"] = int(price_match.group(1))

            # URL
            href = link.get('href', '')
            if href:
                promo["url"] = f"https://shopee.vn{href}" if href.startswith('/') else href

            # Detect electronics category from product name
            if promo["name"]:
                name_lower = promo["name"].lower()
                if any(kw in name_lower for kw in [
                    "điện tử", "phone", "laptop", "tablet", "tai nghe", "sạc",
                    "cáp", "iphone", "samsung", "máy tính", "camera", "loa",
                    "pin", "ốp lưng", "màn hình", "bàn phím", "chuột",
                ]):
                    promo["category"] = "Electronics & Tech"

            if promo["discount_percent"]:
                promo["id"] = generate_promo_id(promo)
                promos.append(promo)

        except Exception as e:
            print(f"Error parsing product deal: {e}")
            continue

    return promos


def parse_flash_sale(html_content, source_url):
    """Parse flash sale items from page HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    promos = []

    items = soup.select(FLASH_SALE_SELECTORS["item"])
    print(f"Found {len(items)} flash sale item elements")

    for item in items:
        try:
            promo = {
                "type": "flash_sale",
                "discount_percent": None,
                "discount_amount": None,
                "min_spend": None,
                "expiry": None,
                "category": None,
                "code": None,
                "source_url": source_url,
                "found_at": datetime.now().isoformat(),
            }

            item_text = item.get_text()

            # Extract discount
            discount_el = item.select_one(FLASH_SALE_SELECTORS["discount"])
            if discount_el:
                discount_text = discount_el.get_text()
                percent_match = re.search(r'(\d+)\s*%', discount_text)
                if percent_match:
                    promo["discount_percent"] = int(percent_match.group(1))

            # Extract name to determine category
            name_el = item.select_one(FLASH_SALE_SELECTORS["name"])
            if name_el:
                name_text = name_el.get_text().lower()
                if any(kw in name_text for kw in ["điện tử", "phone", "laptop", "tablet", "tai nghe", "sạc", "cáp"]):
                    promo["category"] = "Electronics & Tech"

            # Also check full item text for electronics keywords
            text_lower = item_text.lower()
            if any(kw in text_lower for kw in ["điện tử", "electronic", "tech", "iphone", "samsung", "laptop", "tablet"]):
                promo["category"] = "Electronics & Tech"

            if promo["discount_percent"]:
                promo["id"] = generate_promo_id(promo)
                promos.append(promo)

        except Exception as e:
            print(f"Error parsing flash sale item: {e}")
            continue

    return promos


def parse_category_deals(html_content, source_url):
    """Parse deals from electronics category page."""
    soup = BeautifulSoup(html_content, 'html.parser')
    promos = []

    # Look for any discount/voucher/promo elements on the category page
    discount_elements = soup.select('[class*="voucher"], [class*="discount"], [class*="promo"], [class*="coupon"]')
    print(f"Found {len(discount_elements)} discount elements on category page")

    for el in discount_elements:
        try:
            promo = {
                "type": "shop",
                "discount_percent": None,
                "discount_amount": None,
                "min_spend": None,
                "expiry": None,
                "category": "Electronics & Tech",
                "code": None,
                "source_url": source_url,
                "found_at": datetime.now().isoformat(),
            }

            el_text = el.get_text()
            percent_match = re.search(r'(\d+)\s*%', el_text)
            if percent_match:
                promo["discount_percent"] = int(percent_match.group(1))

            amount_match = re.search(r'(\d[\d.]*)\s*[đĐ₫]|[đĐ₫]\s*(\d[\d.]*)', el_text)
            if amount_match:
                amount_str = (amount_match.group(1) or amount_match.group(2)).replace('.', '')
                try:
                    promo["discount_amount"] = int(amount_str)
                except ValueError:
                    pass

            if promo["discount_percent"] or promo["discount_amount"]:
                promo["id"] = generate_promo_id(promo)
                promos.append(promo)

        except Exception as e:
            print(f"Error parsing category deal: {e}")
            continue

    return promos


async def scan_promos(category_filter="electronics"):
    """
    Main promo scanning function.
    Scans Shopee voucher pages, flash sales, and electronics category
    for high-value deals.

    Returns list of promo dicts sorted by highest discount.
    """
    print(f"\nStarting promo scan (filter: {category_filter})...")
    all_new_promos = []

    try:
        async with get_browser_context() as (context, page):
            for url_key, url in PROMO_URLS.items():
                print(f"\n--- Scanning: {url_key} ({url}) ---")
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(5)  # Let JS render
                    await handle_page_challenges(page, max_wait=45)
                    await scroll_page(page, scroll_count=3, delay_ms=2000)

                    html_content = await page.content()

                    # Save raw HTML for debugging
                    debug_file = f"promo_debug_{url_key}.html"
                    with open(debug_file, "w", encoding="utf-8") as f:
                        f.write(html_content)

                    # Parse based on page type
                    if url_key == "voucher":
                        promos = parse_vouchers(html_content, url)
                    elif url_key == "flash_sale":
                        promos = parse_flash_sale(html_content, url)
                    elif url_key == "electronics":
                        promos = parse_category_deals(html_content, url)
                    else:
                        promos = []

                    print(f"Found {len(promos)} promos from {url_key}")
                    all_new_promos.extend(promos)

                except Exception as e:
                    print(f"Error scanning {url_key}: {e}")
                    continue

                # Brief pause between pages
                await asyncio.sleep(3)

    except Exception as e:
        print(f"Browser error during promo scan: {repr(e)}")

    # Filter by category if specified
    if category_filter == "electronics":
        # Keep electronics-specific promos AND platform-wide vouchers (usable on electronics)
        filtered = [p for p in all_new_promos if
                    p.get("category") == "Electronics & Tech" or
                    p.get("type") == "platform"]
        print(f"Filtered to {len(filtered)} electronics-relevant promos (from {len(all_new_promos)} total)")
        all_new_promos = filtered
    elif category_filter == "all":
        pass  # Keep everything

    # Sort by highest discount
    all_new_promos.sort(
        key=lambda x: (x.get("discount_percent") or 0, x.get("discount_amount") or 0),
        reverse=True
    )

    # Merge with history
    history = load_promo_history()
    history = merge_promos(history, all_new_promos)
    save_promo_history(history)
    print(f"Promo history updated: {len(history)} total promos saved")

    return all_new_promos


def get_recent_promos(limit=10):
    """Get most recent promos from history, sorted by discount."""
    history = load_promo_history()
    # Sort by found_at (most recent first), then by discount
    history.sort(
        key=lambda x: (x.get("found_at", ""), x.get("discount_percent") or 0),
        reverse=True
    )
    return history[:limit]


if __name__ == "__main__":
    promos = asyncio.run(scan_promos())
    print(f"\nFound {len(promos)} promos:")
    for p in promos[:10]:
        print(f"  [{p['type']}] {p.get('discount_percent', '?')}% off - Category: {p.get('category', 'General')}")
