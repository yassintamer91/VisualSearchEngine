import os
import csv
import argparse
from pathlib import Path
from PIL import Image
import numpy as np

# Import your Search Engine
from models.search_engine import ImageSearchEngine

def bulk_upload_images(folder_path, csv_mapping_path=None, default_price="N/A", rebuild=False):
    """
    Scans a folder for images and adds them to FAISS.
    If a CSV mapping is provided, it uses the names/prices from the CSV.
    Otherwise, it assigns a generic "Unknown Product" name.
    """
    directory = Path(folder_path)
    if not directory.exists() or not directory.is_dir():
        print(f"Error: Directory '{folder_path}' does not exist.")
        return

    # Load CSV mapping if provided (Format: filename,product_name,price)
    metadata_map = {}
    if csv_mapping_path and os.path.exists(csv_mapping_path):
        with open(csv_mapping_path, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Normalize column names
            fieldnames = [name.strip().lower() for name in reader.fieldnames]
            reader.fieldnames = fieldnames
            
            for row in reader:
                # We expect columns like 'filename', 'name' or 'product_name', 'price'
                filename = row.get('filename', '').strip()
                name = row.get('product_name', row.get('product name', row.get('name', 'Unknown Product'))).strip()
                price = row.get('price', default_price).strip()
                if filename:
                    metadata_map[filename] = {"name": name, "price": price}
        print(f"Loaded mapping for {len(metadata_map)} items from CSV.")
    elif csv_mapping_path:
        print(f"Warning: CSV file '{csv_mapping_path}' not found. Defaulting to generic names.")

    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    image_paths = [p for p in directory.rglob('*') if p.suffix.lower() in valid_extensions]
    
    total_images = len(image_paths)
    if total_images == 0:
        print(f"No images found in '{folder_path}'.")
        return

    print(f"Found {total_images} images. Initializing search engine...")

    engine = ImageSearchEngine()
    import faiss
    if rebuild:
        engine.index = faiss.IndexFlatIP(engine.embedding_dim)
        engine.metadata = []
        print("--rebuild: cleared existing index, starting fresh.")
    elif engine.index is None:
        engine.index = faiss.IndexFlatIP(engine.embedding_dim)
        
    all_features = []
    
    print("\nStarting bulk extraction...")
    for i, file_path in enumerate(image_paths, 1):
        try:
            # Determine product name and price
            filename = file_path.name
            if filename in metadata_map:
                product_name = metadata_map[filename]['name']
                product_price = metadata_map[filename]['price']
            else:
                # Generic name if randomly named and no CSV matched
                product_name = f"Unlabeled Product ({filename})"
                product_price = default_price
            
            # Extract features
            img = Image.open(str(file_path)).convert('RGB')
            features = engine.extract_features(img)
            all_features.append(features)
            
            meta_dict = {
                "path": str(file_path),
                "name": product_name,
                "price": product_price
            }
            engine.metadata.append(meta_dict)
            
            if i % 100 == 0:
                print(f"Processed {i}/{total_images} images...")
                
        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")

    if all_features:
        features_matrix = np.vstack(all_features)
        engine.index.add(features_matrix)
        engine._save_index()
        print(f"\n? Bulk upload complete! FAISS database now contains {engine.index.ntotal} items.")
    else:
        print("\n? No images were successfully processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk upload images to FAISS index.")
    parser.add_argument("folder", type=str, help="Path to your images folder (e.g., imgs)")
    parser.add_argument("--csv", type=str, default=None, help="Path to a CSV file linking filenames to product names")
    parser.add_argument("--price", type=str, default="N/A", help="Default price if not using CSV")
    
    parser.add_argument("--rebuild", action="store_true", help="Clear and rebuild the index from scratch instead of appending")
    args = parser.parse_args()
    bulk_upload_images(args.folder, args.csv, args.price, args.rebuild)
