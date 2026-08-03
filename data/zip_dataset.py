import shutil
import os

def zip_full_dataset():
    source_dir = os.path.join("data", "yolo_full_dataset")
    output_filename = "yolo_full_dataset"
    
    print(f"Zipping {source_dir} to {output_filename}.zip...")
    # Compress the entire datasets folder into a single ZIP file
    shutil.make_archive(output_filename, 'zip', source_dir)
    print("Zip complete! You can now upload yolo_full_dataset.zip to Google Drive.")

if __name__ == "__main__":
    zip_full_dataset()