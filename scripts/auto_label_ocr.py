import os
import csv
import argparse
import warnings

# Suppress warnings from easyocr
warnings.filterwarnings('ignore')

try:
    import easyocr
except ImportError:
    print("EasyOCR is not installed. Please wait for the installation to finish or run: pip install easyocr")
    exit(1)

def generate_auto_labels(img_dir, output_csv):
    """
    Scans a directory of images and uses AI (EasyOCR) to read the product packaging.
    Saves the best guesses into a CSV so you don't have to type them from scratch!
    """
    print("Loading EasyOCR AI models (this might take a moment to download on the first run)...")
    # We use English by default. For Egyptian products, we could add 'ar' (Arabic) by using ['en', 'ar']
    reader = easyocr.Reader(['en', 'ar'])
    
    valid_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    
    if not os.path.exists(img_dir):
        print(f"Error: Directory {img_dir} does not exist.")
        return
        
    files = []
    for root, _, filenames in os.walk(img_dir):
        for f in filenames:
            if os.path.splitext(f)[1].lower() in valid_extensions:
                rel_path = os.path.relpath(os.path.join(root, f), img_dir)
                files.append(rel_path)
    
    if not files:
        print(f"No images found in {img_dir}")
        return
        
    print(f"Found {len(files)} images. Starting AI auto-labeling...")
    
    with open(output_csv, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "product_name", "price"])
        
        for i, filename in enumerate(files):
            img_path = os.path.join(img_dir, filename)
            try:
                # detail=0 returns just the text pieces
                result = reader.readtext(img_path, detail=0)
                
                if result:
                    # Filter out very short meaningless text (like '1', 'g', etc.) if possible, 
                    # but keep it if it's the only thing there. 
                    valid_text = [t for t in result if len(t.strip()) > 1]
                    
                    if valid_text:
                        # Join the top 5 pieces of text found on the packaging
                        product_guess = " ".join(valid_text[:5])
                    else:
                        product_guess = " ".join(result)
                else:
                    product_guess = "" # Left blank if no text is found
                    
            except Exception as e:
                print(f"Failed to read {filename}: {e}")
                product_guess = ""
                
            writer.writerow([filename, product_guess, ""])
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(files)} images...")
                
    print(f"\nDone! Auto-labeled CSV generated at: {output_csv}")
    print("Open the CSV in Excel, fix any OCR typos, add the prices, and then run bulk_upload.py!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-guess product names using OCR.")
    parser.add_argument("img_dir", help="Directory containing the unorganized images")
    parser.add_argument("--out", default="product_mapping_auto.csv", help="Output CSV name")
    args = parser.parse_args()
    
    generate_auto_labels(args.img_dir, args.out)
