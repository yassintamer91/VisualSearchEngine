import os
from bing_image_downloader import downloader

# An example list of common supermarket items to build our database
catalog_items = [
    "Coca Cola 12oz can white background",
    "Campbells Tomato Soup can white background",
    "Skippy Peanut Butter Jar white background",
    "Heinz Tomato Ketchup Bottle white background",
    "Cheerios Box white background",
    "Barilla Spaghetti Box white background",
    "Lays Classic Potato Chips bag white background"
]

output_dir = os.path.join(os.path.dirname(__file__), '..', 'catalog')
os.makedirs(output_dir, exist_ok=True)

print("Starting automated catalog image download...")
for item in catalog_items:
    print(f"\n--- Downloading reference images for: {item} ---")
    downloader.download(
        item, 
        limit=3, 
        output_dir=output_dir, 
        adult_filter_off=True, 
        force_replace=False, 
        timeout=60, 
        verbose=False
    )
print("\nSuccess! All catalog images downloaded.")
