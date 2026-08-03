"""
Download images for product categories that are severely underrepresented in the database.
Uses OpenFoodFacts (open, verified product images).

Run from the project root:
    python scripts/download_missing_categories.py
"""
import csv, time, re, io, requests
from pathlib import Path
from PIL import Image

ROOT_DIR  = Path(__file__).resolve().parent.parent
IMGSS_DIR = ROOT_DIR / 'imgss'
CSV_PATH  = ROOT_DIR / 'products.csv'
HEADERS   = {'User-Agent': 'SupermarketVisualSearch/1.0 (academic project)'}

# (display_name, price_egp, off_search_query, max_images)
MISSING_PRODUCTS = [
    # ── Cereals & Breakfast ────────────────────────────────────────────────
    ("Kellogg's Corn Flakes",           80,  "kellogg's corn flakes",        4),
    ("Kellogg's Frosties",              85,  "kellogg's frosties",            3),
    ("Kellogg's Coco Pops",             85,  "kellogg's coco pops",           3),
    ("Kellogg's Special K",             90,  "kellogg's special k",           3),
    ("Kellogg's Honey Smacks",          85,  "kellogg's honey smacks",        3),
    ("Quaker Oats",                     55,  "quaker oats",                   4),
    ("Quaker Instant Oatmeal",          65,  "quaker instant oatmeal",        3),
    ("Cheerios",                        75,  "cheerios cereal",               4),
    ("Nestle Fitness Cereal",           80,  "nestle fitness cereal",         3),
    ("Muesli",                          65,  "muesli cereal",                 3),
    ("Granola",                         70,  "granola cereal",                3),
    ("Weetabix",                        75,  "weetabix",                      3),
    ("Honey Loops Cereal",              70,  "honey loops cereal",            3),

    # ── Spreads ───────────────────────────────────────────────────────────
    ("Nutella Hazelnut Spread",         85,  "nutella hazelnut spread",       4),
    ("Skippy Peanut Butter",            75,  "skippy peanut butter",          3),
    ("Jif Peanut Butter",               75,  "jif peanut butter",             3),
    ("Sunpat Peanut Butter",            70,  "sunpat peanut butter",          3),
    ("Smucker's Strawberry Jam",        50,  "smucker's strawberry jam",      3),
    ("Bonne Maman Strawberry Jam",      75,  "bonne maman strawberry jam",    3),
    ("Hero Apricot Jam",                55,  "hero apricot jam",              3),
    ("Golden Honey Jar",                55,  "honey jar",                     3),
    ("Lotus Biscoff Spread",            80,  "lotus biscoff spread",          3),
    ("Tahini Sesame Paste",             45,  "tahini sesame paste",           3),

    # ── Pasta & Rice ──────────────────────────────────────────────────────
    ("Barilla Spaghetti",               35,  "barilla spaghetti pasta",       4),
    ("Barilla Penne",                   35,  "barilla penne pasta",           3),
    ("Barilla Fusilli",                 35,  "barilla fusilli pasta",         3),
    ("De Cecco Spaghetti",              45,  "de cecco spaghetti",            3),
    ("Uncle Ben's Basmati Rice",        60,  "uncle ben's basmati rice",      3),
    ("President Basmati Rice",          50,  "president basmati rice",        3),
    ("Lundberg Rice",                   55,  "lundberg rice",                 3),
    ("Indomie Noodles",                 15,  "indomie noodles",               4),
    ("Maggi Noodles",                   15,  "maggi noodles",                 3),
    ("Nissin Cup Noodles",              20,  "nissin cup noodles",            3),

    # ── Canned & Preserved Goods ──────────────────────────────────────────
    ("Heinz Baked Beans",               35,  "heinz baked beans can",         3),
    ("Heinz Tomato Soup",               30,  "heinz tomato soup can",         3),
    ("Campbell's Tomato Soup",          35,  "campbell's tomato soup",        3),
    ("John West Tuna in Spring Water",  45,  "john west tuna can",            3),
    ("Princes Tuna in Sunflower Oil",   40,  "princes tuna can",              3),
    ("Del Monte Sweet Corn",            30,  "del monte sweet corn can",      3),
    ("Heinz Tomato Ketchup",            45,  "heinz tomato ketchup bottle",   4),
    ("Mutti Tomato Passata",            35,  "mutti tomato passata",          3),
    ("Cirio Crushed Tomatoes",          30,  "cirio crushed tomatoes can",    3),
    ("Green Giant Sweet Corn",          35,  "green giant sweet corn",        3),
    ("Bonduelle Green Peas",            30,  "bonduelle green peas can",      3),
    ("Al-Barakah Chickpeas",            15,  "chickpeas canned",              3),

    # ── Dairy & Yogurt ───────────────────────────────────────────────────
    ("Activia Strawberry Yogurt",       25,  "activia strawberry yogurt",     4),
    ("Danone Natural Yogurt",           20,  "danone natural yogurt",         3),
    ("Yoplait Strawberry Yogurt",       22,  "yoplait strawberry yogurt",     3),
    ("Philadelphia Cream Cheese",       75,  "philadelphia cream cheese",     4),
    ("Laughing Cow Cheese",             55,  "laughing cow cheese",           3),
    ("Lurpak Butter",                   65,  "lurpak butter",                 3),
    ("President Butter",                60,  "president butter",              3),
    ("Elle & Vire Cream",               35,  "elle vire cream",               3),
    ("Puck Cream Cheese",               55,  "puck cream cheese",             3),
    ("Happy Cow Cheese",                45,  "happy cow cheese slices",       3),

    # ── Baby Products ─────────────────────────────────────────────────────
    ("Pampers Active Baby Diapers",     150, "pampers active baby diapers",   3),
    ("Huggies Diapers",                 145, "huggies diapers",               3),
    ("Nestle Cerelac",                  80,  "nestle cerelac baby food",      3),
    ("Gerber Baby Food",                55,  "gerber baby food jar",          3),
    ("Aptamil Baby Formula",            200, "aptamil baby formula",          3),

    # ── Condiments & Sauces ───────────────────────────────────────────────
    ("Hellmann's Mayonnaise",           60,  "hellmann's mayonnaise jar",     3),
    ("Knorr Chicken Stock Cubes",       25,  "knorr chicken stock cubes",     3),
    ("Tabasco Hot Sauce",               45,  "tabasco hot sauce bottle",      3),
    ("Maggi Seasoning Sauce",           25,  "maggi seasoning sauce",         3),
    ("Lea & Perrins Worcestershire",    55,  "lea perrins worcestershire",    3),

    # ── Household & Cleaning ─────────────────────────────────────────────
    ("Ariel Laundry Powder",            90,  "ariel laundry powder box",      3),
    ("Persil Laundry Detergent",        85,  "persil laundry detergent",      3),
    ("Fairy Dish Soap",                 45,  "fairy dish soap bottle",        3),
    ("Dettol Soap",                     25,  "dettol antibacterial soap",     3),
    ("Downy Fabric Softener",           75,  "downy fabric softener",         3),

    # ── Personal Care ─────────────────────────────────────────────────────
    ("Head & Shoulders Shampoo",        85,  "head shoulders shampoo",        3),
    ("Pantene Shampoo",                 80,  "pantene shampoo bottle",        3),
    ("Dove Body Wash",                  60,  "dove body wash",                3),
    ("Colgate Toothpaste",              55,  "colgate toothpaste",            3),
    ("Oral-B Toothbrush",               45,  "oral-b toothbrush",             3),
    ("Nivea Body Lotion",               80,  "nivea body lotion",             3),
    ("Gillette Razor",                  90,  "gillette razor",                3),
    ("Always Sanitary Pads",            60,  "always sanitary pads",          3),

    # ── Frozen & Ice Cream ────────────────────────────────────────────────
    ("Magnum Classic Ice Cream",        60,  "magnum classic ice cream",      4),
    ("Cornetto Ice Cream",              35,  "cornetto ice cream cone",       3),
    ("Haagen-Dazs Ice Cream",           120, "haagen dazs ice cream",         3),
    ("Ben & Jerry's Ice Cream",         120, "ben jerry's ice cream",         3),
    ("Carte D'Or Vanilla Ice Cream",    75,  "carte d'or vanilla ice cream",  3),
]


def search_off(query, page_size=15, retries=3):
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {"search_terms": query, "search_simple": 1, "action": "process",
              "json": 1, "page_size": page_size,
              "fields": "product_name,image_url,image_front_url"}
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json().get("products", [])
        except Exception as e:
            wait = 4 * (attempt + 1)
            print(f"    Retry {attempt+1} ({e}) — waiting {wait}s")
            time.sleep(wait)
    return []


def fetch_image(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content))
        img.verify()
        return r.content
    except Exception:
        return None


def sanitize(name):
    return re.sub(r'[\\/:*?"<>| ]', '_', name).lower()


def run():
    IMGSS_DIR.mkdir(exist_ok=True)
    existing_files = {f.name for f in IMGSS_DIR.iterdir()}

    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        existing_rows = list(csv.DictReader(f))
    existing_csv = {r['Filename'] for r in existing_rows}

    new_rows = []
    total = 0

    for product_name, price, query, max_img in MISSING_PRODUCTS:
        print(f"\n[{product_name}]")
        products = search_off(query, page_size=20)
        saved = 0

        for prod in products:
            if saved >= max_img:
                break
            url = prod.get('image_front_url') or prod.get('image_url')
            if not url:
                continue
            fname = f"cat_{sanitize(product_name)}_{saved+1}.jpg"
            if fname in existing_files or fname in existing_csv:
                saved += 1
                continue
            data = fetch_image(url)
            if not data:
                continue
            (IMGSS_DIR / fname).write_bytes(data)
            existing_files.add(fname)
            new_rows.append({'Subfolder': 'imgss', 'Filename': fname,
                             'Product Name': product_name, 'Price': str(price)})
            saved += 1
            total += 1
            print(f"  saved {fname}")
            time.sleep(0.3)

        if saved == 0:
            print(f"  no images found")

    if new_rows:
        all_rows = existing_rows + new_rows
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['Subfolder','Filename','Product Name','Price'])
            writer.writeheader()
            writer.writerows(all_rows)
        print(f"\nAdded {total} images to imgss/ and products.csv")
        print("Rebuild index:  python scripts/build_faiss_index.py")
    else:
        print("\nNo new images added.")


if __name__ == '__main__':
    print(f"Downloading {len(MISSING_PRODUCTS)} missing product categories from OpenFoodFacts...")
    run()
