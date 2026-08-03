from ultralytics import YOLO
import sys

def train_yolo(data_yaml_path="coco8.yaml"):
    """
    Train a YOLOv8 nano model on a dataset.
    If 'coco8.yaml' is provided, Ultralytics will automatically download
    a tiny 8-image version of the COCO dataset which contains supermarket 
    items like 'apple', 'orange', 'broccoli', 'carrot', 'bottle', etc.
    This lets you test the full pipeline today without waiting for huge downloads.
    """
    # Load a pretrained nano model (fastest, ideal for CPU/laptop and quick iteration)
    model = YOLO("yolov8n.pt")
    
    # Train the model
    # Limiting epochs and image size for rapid prototyping
    print(f"Starting YOLO training using dataset config: {data_yaml_path}")
    results = model.train(
        data=data_yaml_path,
        epochs=10, 
        imgsz=640,
        batch=8,
        device="cpu", # change to 'cuda' or 0 if you have a GPU
        project="models/runs",
        name="initial_yolo_model"
    )
    
    print(f"\nTraining complete. Model saved to {results.save_dir}/weights/best.pt")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        yaml_path = sys.argv[1]
    else:
        yaml_path = "coco8.yaml"
        print("No dataset provided. Defaulting to 'coco8.yaml' for a quick functional test.")
        
    train_yolo(yaml_path)