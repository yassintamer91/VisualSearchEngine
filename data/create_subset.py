import os
import random
import shutil

def create_subset(src_dir, dest_dir, percentage=0.1):
    print(f"Creating a {percentage*100}% subset from {src_dir} into {dest_dir}...")
    
    # Define paths
    splits = ["train", "val", "test"]
    
    for split in splits:
        src_images_dir = os.path.join(src_dir, "images", split)
        src_labels_dir = os.path.join(src_dir, "labels", split)
        
        dest_images_dir = os.path.join(dest_dir, "images", split)
        dest_labels_dir = os.path.join(dest_dir, "labels", split)
        
        os.makedirs(dest_images_dir, exist_ok=True)
        os.makedirs(dest_labels_dir, exist_ok=True)
        
        if not os.path.exists(src_images_dir):
            continue
            
        # Get all images in the split
        images = [f for f in os.listdir(src_images_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        
        # Calculate how many images to sample
        num_samples = max(1, int(len(images) * percentage))
        sampled_images = random.sample(images, num_samples)
        
        print(f"[{split}] Sampling {num_samples} out of {len(images)} images.")
        
        # Copy images and corresponding labels
        for img in sampled_images:
            # Copy image
            shutil.copy2(os.path.join(src_images_dir, img), os.path.join(dest_images_dir, img))
            
            # Copy label (if it exists)
            label_file = os.path.splitext(img)[0] + ".txt"
            src_label_path = os.path.join(src_labels_dir, label_file)
            if os.path.exists(src_label_path):
                shutil.copy2(src_label_path, os.path.join(dest_labels_dir, label_file))

if __name__ == "__main__":
    src = os.path.join("data", "yolo_full_dataset")
    dest = os.path.join("data", "yolo_subset_dataset")
    create_subset(src, dest, 0.1)  # 10%
    
    # Create the subset YAML file
    with open(os.path.join(src, "full_dataset.yaml"), "r") as f:
        yaml_content = f.read()
    
    # Update the path to point to subset
    yaml_content = yaml_content.replace("yolo_full_dataset", "yolo_subset_dataset")
    
    with open(os.path.join(dest, "subset_dataset.yaml"), "w") as f:
        f.write(yaml_content)
    
    print("\nSubset completely generated! Saved subset YAML config.")
