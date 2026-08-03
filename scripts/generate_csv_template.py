import os
import csv
import argparse
from pathlib import Path

def generate_csv_template(folder_path, output_csv="product_mapping.csv"):
    """
    Scans a folder for image files and generates a ready-to-use CSV template.
    """
    directory = Path(folder_path)
    if not directory.exists() or not directory.is_dir():
        print(f"Error: Directory '{folder_path}' does not exist.")
        return

    # Look for common image formats
    valid_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    image_filenames = [p.name for p in directory.rglob('*') if p.suffix.lower() in valid_extensions]
    
    total_images = len(image_filenames)
    if total_images == 0:
        print(f"No images found in '{folder_path}'.")
        return

    print(f"Found {total_images} images. Generating CSV template...")
    
    # Write to CSV
    with open(output_csv, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Write headers required by the bulk_upload script
        writer.writerow(['filename', 'product_name', 'price'])
        
        # Populate each row with the file name and empty placeholders
        for img in image_filenames:
            writer.writerow([img, '', ''])

    print(f"\n? Success! Created '{output_csv}' with {total_images} rows.")
    print("Next steps:")
    print(f"1. Open '{output_csv}' in Excel or Google Sheets.")
    print("2. Type the real product names into the empty 'product_name' column.")
    print("3. (Optional) Add prices to the 'price' column.")
    print("4. Save and run the bulk_upload.py script with the --csv flag!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a CSV template to map randomly named images to actual products.")
    parser.add_argument("folder", type=str, help="Absolute path to the folder containing your images")
    parser.add_argument("--out", type=str, default="product_mapping.csv", help="Output file name/path (default: product_mapping.csv)")
    
    args = parser.parse_args()
    generate_csv_template(args.folder, args.out)
