import json
import os
import shutil
from pathlib import Path

def convert_coco_to_yolo_split(coco_json_path, images_dir, output_dir, split_name="train", category_ids=None):
    """
    Converts a COCO format dataset split (train/val/test) into YOLO format.
    """
    print(f"Loading annotations from {coco_json_path}...")
    with open(coco_json_path, 'r') as f:
        coco_data = json.load(f)

    # Use provided categories or build from this JSON
    if category_ids is None:
        categories = coco_data['categories']
        category_ids = {cat['id']: idx for idx, cat in enumerate(categories)}
        category_names = {idx: cat['name'] for idx, cat in enumerate(categories)}
    else:
        categories = [{'id': k, 'name': v} for k, v in category_ids.items()] # Mock for simplicity
        
    print(f"Processing {len(coco_data['images'])} images and {len(coco_data['annotations'])} annotations for '{split_name}' split...")

    # Create YOLO output directories for this split
    images_out = Path(output_dir) / 'images' / split_name
    labels_out = Path(output_dir) / 'labels' / split_name
    images_out.mkdir(parents=True, exist_ok=True)
    labels_out.mkdir(parents=True, exist_ok=True)

    # Map image_id to file_name and dimensions
    image_info = {img['id']: img for img in coco_data['images']}

    # Group annotations by image
    from collections import defaultdict
    ann_by_img = defaultdict(list)
    for ann in coco_data['annotations']:
        if ann['category_id'] in category_ids:
            ann_by_img[ann['image_id']].append(ann)

    # Process annotations and write YOLO txt files
    for img_id, img_data in image_info.items():
        file_name = img_data['file_name']
        img_w = img_data['width']
        img_h = img_data['height']
        
        # Write format: class x_center y_center width height
        label_file = labels_out / f"{Path(file_name).stem}.txt"
        
        # Only write if there are annotations
        if img_id in ann_by_img:
            with open(label_file, 'w') as f:
                for ann in ann_by_img[img_id]:
                    x_min, y_min, w, h = ann['bbox']
                    x_center = (x_min + w / 2) / img_w
                    y_center = (y_min + h / 2) / img_h
                    norm_w = w / img_w
                    norm_h = h / img_h
                    
                    yolo_class_id = category_ids[ann['category_id']]
                    f.write(f"{yolo_class_id} {x_center} {y_center} {norm_w} {norm_h}\n")
        else:
            # Empty file for background images (optional, but good for YOLO)
            open(label_file, 'w').close()
            
        # Copy image
        src_img = Path(images_dir) / file_name
        dest_img = images_out / file_name
        if not dest_img.exists() and src_img.exists():
            shutil.copy(src_img, dest_img)

    return category_ids

def create_yaml(output_dir, category_ids):
    yaml_path = Path(output_dir) / 'full_dataset.yaml'
    with open(yaml_path, 'w') as f:
        f.write(f"path: {os.path.abspath(output_dir)}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write("test: images/test\n\n")
        f.write("names:\n")
        # Reverse mapping to get names
        for original_id, yolo_id in category_ids.items():
            f.write(f"  {yolo_id}: 'product_{original_id}'\n") # Update if you have exact names
            
    print(f"\nYOLO configuration saved to {yaml_path}")

if __name__ == "__main__":
    # ==========================================
    # UPDATE THESE PATHS TO YOUR 3 NEW DATASETS
    # ==========================================
    
    # 1. Training Set
    TRAIN_JSON = 'C:/Users/ytame/Downloads/archive (1)/instances_train2019.json'
    TRAIN_IMGS = 'C:/Users/ytame/Downloads/archive (1)/train2019'
    
    # 2. Validation Set
    VAL_JSON = 'C:/Users/ytame/Downloads/archive (1)/instances_val2019.json'
    VAL_IMGS = 'C:/Users/ytame/Downloads/archive (1)/val2019'
    
    # 3. Testing Set
    TEST_JSON = 'C:/Users/ytame/Downloads/archive (1)/instances_test2019.json'
    TEST_IMGS = 'C:/Users/ytame/Downloads/archive (1)/test2019'
    
    # Where to save the full YOLO formatted output
    OUTPUT_DIR = 'data/yolo_full_dataset'

    print("Starting full dataset conversion...")
    
    # Needs to extract global category mapping from train set first to keep IDs consistent
    print("\n--- Processing Training Set ---")
    cat_ids = convert_coco_to_yolo_split(TRAIN_JSON, TRAIN_IMGS, OUTPUT_DIR, "train")
    
    print("\n--- Processing Validation Set ---")
    convert_coco_to_yolo_split(VAL_JSON, VAL_IMGS, OUTPUT_DIR, "val", category_ids=cat_ids)
    
    print("\n--- Processing Testing Set ---")
    convert_coco_to_yolo_split(TEST_JSON, TEST_IMGS, OUTPUT_DIR, "test", category_ids=cat_ids)
    
    create_yaml(OUTPUT_DIR, cat_ids)
    print("\n✅ Conversion Complete! You are ready to train.")
