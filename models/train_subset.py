from ultralytics import YOLO

def train_yolo_subset():
    print("Loading YOLOv8n model to begin fine-tuning...")
    # Load a pretrained model
    model = YOLO("yolov8n.pt") 

    print("Initiating subset training... Buckle up!")
    # Train the model with a 10% subset for 100 epochs
    results = model.train(
        data="data/yolo_subset_dataset/subset_dataset.yaml", 
        epochs=100,           # Set exactly to 100 epochs
        imgsz=640,            # Image resolution
        batch=16,             # Batch size
        device="cpu",         # Assuming CPU as you used previously. Change to device=0 if you have a configured GPU
        name="subset_10pct_100ep" # This will save results under runs/detect/subset_10pct_100ep
    )
    print("\nTraining on 10% dataset complete!")

if __name__ == "__main__":
    train_yolo_subset()