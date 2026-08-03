import os
import sys
import urllib.request

# Add the current directory so Python can find the models module
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from models.search_engine import ImageSearchEngine

# The folder where we will store the reference images of our products
CATALOG_DIR = os.path.join("app", "static", "catalog")

def download_sample_images():
    """Downloads some generic supermarket items to test the search database."""
    os.makedirs(CATALOG_DIR, exist_ok=True)
    samples = {
        "coke_bottle.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e8/Coca-Cola_bottle_transparent.png/400px-Coca-Cola_bottle_transparent.png",
        "red_apple.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Red_Apple.jpg/400px-Red_Apple.jpg",
        "orange.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c4/Orange-Fruit-Pieces.jpg/400px-Orange-Fruit-Pieces.jpg",
        "broccoli.jpg": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/03/Broccoli_and_cross_section_edit.jpg/400px-Broccoli_and_cross_section_edit.jpg"
    }
    
    for name, url in samples.items():
        path = os.path.join(CATALOG_DIR, name)
        if not os.path.exists(path):
            try:
                print(f"Downloading sample {name}...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception as e:
                print(f"Failed to download {name}: {e}")

def main():
    print("--- Supermarket Catalog Indexer ---")
    
    # 1. Ensure the directory exists and has some files
    os.makedirs(CATALOG_DIR, exist_ok=True)
    if len(os.listdir(CATALOG_DIR)) == 0:
        print("Catalog directory is empty. Downloading sample images...")
        download_sample_images()
        
    # 2. Gather image paths
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    image_paths = []
    
    for file in os.listdir(CATALOG_DIR):
        ext = os.path.splitext(file)[1].lower()
        if ext in valid_exts:
            # Maintain path relative to workspace root (e.g. app/static/catalog/image.jpg)
            path = os.path.join(CATALOG_DIR, file).replace("\\", "/")
            image_paths.append(path)
                
    if not image_paths:
        print(f"No images found in {CATALOG_DIR}. Please add some product pictures and run again.")
        return
        
    print(f"Found {len(image_paths)} images in the catalog. Extracting features...")
    
    # 3. Build FAISS Index
    engine = ImageSearchEngine()
    engine.build_index(image_paths)
    print("✅ Indexing complete! The visual search database is ready.")

if __name__ == "__main__":
    main()