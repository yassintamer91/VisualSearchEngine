"""
Download beverage product images from OpenFoodFacts (open, verified product database)
and add them to imgss/ + products.csv.

Run from the project root:
    python scripts/download_beverages.py
"""
import os
import csv
import time
import shutil
import requests
from pathlib import Path
from PIL import Image
import io

ROOT_DIR  = Path(__file__).resolve().parent.parent
IMGSS_DIR = ROOT_DIR / 'imgss'
CSV_PATH  = ROOT_DIR / 'products.csv'

HEADERS = {'User-Agent': 'SupermarketVisualSearch/1.0 (academic project)'}

# Each entry: (display_name, price_egp, off_search_query, max_images)
# We search OpenFoodFacts by product name and take the best results.
BEVERAGES = [
    # Carbonated
    ("Coca-Cola Can",               20,  "coca-cola can",            4),
    ("Pepsi Can",                   20,  "pepsi can",                4),
    ("Sprite Can",                  20,  "sprite can",               3),
    ("Fanta Orange",                20,  "fanta orange",             3),
    ("7UP Can",                     20,  "7up can",                  3),
    ("Mirinda Orange",              20,  "mirinda orange",           3),
    ("Mountain Dew Can",            22,  "mountain dew",             3),
    ("Coca-Cola Zero",              20,  "coca cola zero",           3),
    ("Pepsi Max",                   20,  "pepsi max",                3),
    ("Schweppes Tonic Water",       25,  "schweppes tonic",          3),

    # Energy drinks
    ("Red Bull Energy Drink",       55,  "red bull energy",          4),
    ("Monster Energy",              55,  "monster energy",           4),
    ("Sting Energy Drink",          25,  "sting energy drink",       3),
    ("Power Horse Energy Drink",    35,  "power horse energy",       3),

    # Juices & nectars
    ("Minute Maid Orange Juice",    25,  "minute maid orange",       4),
    ("Tropicana Orange Juice",      40,  "tropicana orange juice",   4),
    ("Capri-Sun Orange",            20,  "capri sun orange",         3),
    ("Cappy Orange Juice",          20,  "cappy orange",             3),
    ("V8 Vegetable Juice",          30,  "v8 vegetable juice",       3),
    ("Almarai Orange Juice",        25,  "almarai orange juice",     3),

    # Water
    ("Nestle Pure Life Water",      10,  "nestle pure life water",   3),
    ("Aquafina Water",              10,  "aquafina water",           3),
    ("Evian Water",                 25,  "evian water",              3),
    ("Dasani Water",                 8,  "dasani water",             3),
    ("Volvic Water",                20,  "volvic water",             3),

    # Milk drinks & dairy beverages
    ("Nesquik Chocolate Milk",      35,  "nesquik chocolate milk",   3),
    ("Nestle Milo",                 45,  "milo chocolate drink",     3),
    ("Nido Powdered Milk",          95,  "nido powdered milk",       3),
    ("Almarai Full Fat Milk",       30,  "almarai milk",             3),

    # Hot drinks (packaged)
    ("Nescafe Classic",             120, "nescafe classic",          3),
    ("Nescafe Gold",                180, "nescafe gold",             3),
    ("Lipton Yellow Label Tea",     40,  "lipton yellow label",      3),
    ("Ahmad Tea",                   60,  "ahmad tea",                3),
    ("Jacobs Coffee",               150, "jacobs coffee",            3),

    # RTD coffee & iced tea
    ("Nescafe Ready to Drink",      25,  "nescafe ready to drink",   3),
    ("Nestea Iced Tea",             18,  "nestea iced tea",          3),
    ("Lipton Ice Tea",              20,  "lipton ice tea",           3),
    ("Arizona Iced Tea",            30,  "arizona iced tea",         3),

    # Sports & flavored drinks
    ("Powerade",                    25,  "powerade sports drink",    3),
    ("Gatorade",                    30,  "gatorade",                 3),
    ("Vimto Fruit Drink",           18,  "vimto",                    3),
    ("Ribena Blackcurrant",         20,  "ribena",                   3),
]


def search_off(query: str, page_size: int = 10, retries: int = 3):
    """Search OpenFoodFacts and return a list of products with image URLs."""
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": page_size,
        "fields": "product_name,image_url,image_front_url",
    }
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json().get("products", [])
        except Exception as e:
            wait = 3 * (attempt + 1)
            print(f"    Attempt {attempt+1} failed ({e}). Retrying in {wait}s...")
            time.sleep(wait)
    print(f"    Giving up on '{query}'")
    return []


def download_image(url: str) -> bytes | None:
    """Download image bytes from URL. Returns None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def is_valid_image(data: bytes) -> bool:
    """Check the bytes are a readable image."""
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        return True
    except Exception:
        return False


def sanitize(name: str) -> str:
    import re
    return re.sub(r'[\\/:*?"<>| ]', '_', name).lower()


def run():
    IMGSS_DIR.mkdir(exist_ok=True)

    # Load existing filenames to avoid duplicates
    existing_files = {f.name for f in IMGSS_DIR.iterdir()} if IMGSS_DIR.exists() else set()

    # Load existing CSV
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        existing_rows = list(csv.DictReader(f))
    existing_csv_files = {r['Filename'] for r in existing_rows}

    new_rows = []
    total_saved = 0

    for product_name, price, query, max_img in BEVERAGES:
        print(f"\n[{product_name}]  query: '{query}'")
        products = search_off(query, page_size=20)

        saved = 0
        for prod in products:
            if saved >= max_img:
                break

            img_url = prod.get('image_front_url') or prod.get('image_url')
            if not img_url:
                continue

            # Build filename
            fname = f"bev_{sanitize(product_name)}_{saved + 1}.jpg"
            if fname in existing_files or fname in existing_csv_files:
                saved += 1
                continue

            data = download_image(img_url)
            if data is None or not is_valid_image(data):
                continue

            dest = IMGSS_DIR / fname
            dest.write_bytes(data)
            existing_files.add(fname)

            new_rows.append({
                'Subfolder':    'imgss',
                'Filename':     fname,
                'Product Name': product_name,
                'Price':        str(price),
            })
            saved += 1
            total_saved += 1
            print(f"  saved {fname}")
            time.sleep(0.3)   # be polite to the API

        if saved == 0:
            print(f"  no images found")

    # Append new rows to CSV
    if new_rows:
        all_rows = existing_rows + new_rows
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Subfolder', 'Filename', 'Product Name', 'Price'])
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nAdded {total_saved} beverage images to imgss/ and products.csv")
        print("Now rebuild the FAISS index:")
        print("  python scripts/build_faiss_index.py")
    else:
        print("\nNo new images added.")


if __name__ == '__main__':
    print(f"Fetching images for {len(BEVERAGES)} beverage products from OpenFoodFacts...")
    run()
