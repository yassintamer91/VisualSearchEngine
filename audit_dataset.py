import os
import glob

def check_dataset():
    label_files = glob.glob('data/yolo_full_dataset/labels/**/*.txt', recursive=True)
    if not label_files:
        print("No label files found. Are they extracted correctly?")
        return

    print(f"Found {len(label_files)} label files. Analyzing...")

    total_boxes = 0
    small_boxes = 0
    class_counts = {}

    for fpath in label_files:
        with open(fpath, 'r') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    cls_id = int(parts[0])
                    w = float(parts[3])
                    h = float(parts[4])
                    
                    total_boxes += 1
                    class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                    
                    # YOLO boxes are normalized 0.0 to 1.0. 
                    # If an object is less than 5% of image width/height, it's quite small.
                    if w < 0.05 or h < 0.05:
                        small_boxes += 1

    print("\n--- Diagnostic Results ---")
    print(f"Total Bounding Boxes: {total_boxes}")
    print(f"Total Unique Classes Found in Labels: {len(class_counts)}")
    min_class = min(class_counts.keys()) if class_counts else -1
    max_class = max(class_counts.keys()) if class_counts else -1
    print(f"Class ID Range: {min_class} to {max_class}")
    
    if total_boxes > 0:
        print(f"Percentage of 'Small' Objects (<5% of image size): {(small_boxes/total_boxes)*100:.2f}%")
        
    # Check severe imbalance
    if class_counts:
        counts = list(class_counts.values())
        print(f"Most frequent class count: {max(counts)}")
        print(f"Least frequent class count: {min(counts)}")

if __name__ == '__main__':
    check_dataset()
