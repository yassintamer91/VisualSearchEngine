"""
Build (or rebuild) the FAISS product index from imgss/ using product names from products.csv.

Run from the project root:
    python scripts/build_faiss_index.py           # fast, one entry per image
    python scripts/build_faiss_index.py --augment # adds +-10deg rotation entries (~3x slower)
"""
import os
import sys
import csv
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.search_engine import ImageSearchEngine

ROOT_DIR  = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
IMGSS_DIR = os.path.join(ROOT_DIR, 'imgss')
CSV_PATH  = os.path.join(ROOT_DIR, 'products.csv')
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}


def load_csv_metadata():
    """Return a dict mapping filename -> {name, price} from products.csv."""
    mapping = {}
    if not os.path.exists(CSV_PATH):
        print(f"Warning: products.csv not found at {CSV_PATH} — names will be empty.")
        return mapping
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalise column names to lowercase
            row = {k.strip().lower(): v.strip() for k, v in row.items()}
            filename = row.get('filename', '')
            name  = row.get('product name', '') or row.get('name', '')
            price = row.get('price', 'N/A')
            if filename:
                mapping[filename] = {'name': name, 'price': price}
    print(f"Loaded {len(mapping)} product entries from products.csv")
    return mapping


def build_knowledge_base(augment=False):
    if not os.path.isdir(IMGSS_DIR):
        print(f"Error: imgss/ directory not found at {IMGSS_DIR}")
        return

    csv_meta = load_csv_metadata()

    image_paths = sorted([
        os.path.join(IMGSS_DIR, f)
        for f in os.listdir(IMGSS_DIR)
        if os.path.splitext(f)[1].lower() in IMAGE_EXTS
    ])

    if not image_paths:
        print("No images found in imgss/.")
        return

    # Build parallel metadata list aligned with image_paths
    metadata_list = []
    missing = 0
    for path in image_paths:
        fname = os.path.basename(path)
        info  = csv_meta.get(fname, {})
        if not info:
            missing += 1
        metadata_list.append({
            'path':  path,
            'name':  info.get('name', os.path.splitext(fname)[0]),
            'price': info.get('price', 'N/A'),
        })

    print(f"Found {len(image_paths)} images ({missing} without a CSV entry).")
    engine = ImageSearchEngine()
    engine.build_index(image_paths, metadata_list=metadata_list, augment=augment)
    print("Done. FAISS index saved to data/embeddings/")
    if not augment:
        print("Tip: re-run with --augment to add rotation variants (~3x entries, better recall).")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--augment', action='store_true',
                        help='Add +-10 deg rotation entries per image (3x entries, ~3x slower)')
    args = parser.parse_args()
    build_knowledge_base(augment=args.augment)
