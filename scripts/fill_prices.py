"""
Assign approximate EGP prices to products.csv based on product-name keywords.

Prices are mid-range estimates for the Egyptian retail market (2024).
Run from the project root:
    python scripts/fill_prices.py
"""
import csv
import os
import re

CSV_PATH = os.path.join(os.path.dirname(__file__), '..', 'products.csv')

# (keywords_in_name, price_egp)
# Rules are checked in order; first match wins.
PRICE_RULES = [
    # ── Chocolates & confectionery ──────────────────────────────────────────
    (["ferrero rocher", "raffaello", "mon cheri"],          85),
    (["kinder bueno"],                                       25),
    (["kinder joy"],                                         20),
    (["kinder"],                                             18),
    (["lindt excellence", "lindt swiss"],                    95),
    (["lindt"],                                              75),
    (["cadbury dairy milk", "cadbury silk"],                 55),
    (["cadbury flake", "cadbury roses", "cadbury"],          35),
    (["merci"],                                              120),
    (["toblerone"],                                          85),
    (["kitkat chunky", "kitkat"],                            25),
    (["snickers", "twix", "bounty", "mars", "milky way"],   25),
    (["lion bar"],                                           22),
    (["galaxy", "dove chocolate"],                           35),
    (["duplo", "hanuta"],                                    22),
    (["haribo"],                                             45),
    (["smarties", "m&m"],                                    30),
    (["oreo"],                                               30),
    (["corona chocolate", "corona milk", "corona white"],    12),
    (["molto"],                                              20),
    (["trident", "orbit gum", "extra gum", "5 gum"],        15),
    (["mentos"],                                             15),
    (["tic tac"],                                            12),
    (["lollipop", "chupa chups"],                            10),
    (["gummy", "jelly"],                                     25),
    (["chocolate"],                                          30),

    # ── Chips & snacks ──────────────────────────────────────────────────────
    (["pringles"],                                           65),
    (["lays", "lay's"],                                      30),
    (["doritos"],                                            35),
    (["cheetos"],                                            25),
    (["takis"],                                              40),
    (["spuds"],                                              30),
    (["tortilla", "nachos"],                                 30),
    (["popcorn"],                                            20),
    (["pretzels"],                                           25),
    (["rice cakes"],                                         25),
    (["nuts", "cashew", "almond", "peanut"],                 45),
    (["chips", "crisps", "snack"],                           25),

    # ── Biscuits & cookies ──────────────────────────────────────────────────
    (["digestive"],                                          35),
    (["tea biscuit", "marie"],                               20),
    (["biscuit", "cookie", "cracker", "wafer"],              25),

    # ── Beverages ───────────────────────────────────────────────────────────
    (["red bull"],                                           55),
    (["monster energy"],                                     55),
    (["coca cola", "pepsi", "7up", "sprite", "fanta"],       20),
    (["tropicana", "minute maid"],                           35),
    (["nesquik", "milo"],                                    45),
    (["nescafe", "jacobs", "lavazza", "starbucks coffee"],   80),
    (["tea", "lipton", "ahmad tea"],                         40),
    (["water"],                                              10),
    (["juice"],                                              25),
    (["energy drink"],                                       50),
    (["milk"],                                               30),

    # ── Dairy ───────────────────────────────────────────────────────────────
    (["philadelphia cream cheese"],                          75),
    (["laughing cow", "la vache"],                           55),
    (["cheese"],                                             50),
    (["yogurt", "yoghurt"],                                  25),
    (["butter"],                                             40),

    # ── Cereals & breakfast ──────────────────────────────────────────────────
    (["kellogg", "corn flakes", "frosties", "coco pops"],    80),
    (["cheerios"],                                           75),
    (["granola", "muesli"],                                  65),
    (["oats", "quaker"],                                     55),
    (["cereal"],                                             70),

    # ── Spreads & condiments ────────────────────────────────────────────────
    (["nutella"],                                            85),
    (["peanut butter", "skippy"],                            75),
    (["jam", "marmalade"],                                   40),
    (["honey"],                                              55),
    (["ketchup", "heinz"],                                   45),
    (["mayonnaise"],                                         40),
    (["mustard"],                                            35),
    (["sauce", "salsa", "dip"],                              35),

    # ── Personal care ───────────────────────────────────────────────────────
    (["shampoo", "conditioner"],                             85),
    (["toothpaste", "toothbrush"],                           55),
    (["deodorant", "antiperspirant"],                        75),
    (["soap", "body wash", "shower gel"],                    60),
    (["lotion", "cream", "moisturizer"],                     80),
    (["sunscreen", "spf"],                                   120),
    (["razor", "gillette"],                                  90),
    (["tissue", "kleenex"],                                  35),

    # ── Household & cleaning ────────────────────────────────────────────────
    (["detergent", "ariel", "persil", "tide"],               90),
    (["fabric softener", "downy", "comfort"],                75),
    (["dish soap", "fairy"],                                 45),
    (["bleach"],                                             30),
    (["air freshener", "febreze"],                           85),

    # ── Baby products ────────────────────────────────────────────────────────
    (["pampers", "huggies", "diapers", "nappies"],           150),
    (["baby food", "gerber"],                                55),

    # ── Default ─────────────────────────────────────────────────────────────
    ([],                                                     30),   # fallback
]


def assign_price(name: str) -> int:
    lower = name.lower()
    for keywords, price in PRICE_RULES:
        if not keywords:          # fallback rule
            return price
        if any(kw in lower for kw in keywords):
            return price
    return 30   # safety fallback


def fill_prices():
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    fieldnames = ['Subfolder', 'Filename', 'Product Name', 'Price']
    filled = skipped = 0

    for row in rows:
        current = row.get('Price', '').strip()
        if current in ('N/A', 'null', '', 'n/a'):
            row['Price'] = assign_price(row.get('Product Name', ''))
            filled += 1
        else:
            skipped += 1

    with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. Prices filled: {filled}, already had price: {skipped}")
    print(f"Updated {CSV_PATH}")


if __name__ == '__main__':
    fill_prices()
