from ultralytics import YOLO
import os

def evaluate_kaggle_model():
    weights_path = 'best (3).pt'
    yaml_path = os.path.join('data', 'yolo_full_dataset', 'full_dataset.yaml')
    
    if not os.path.exists(weights_path):
        print(f"Error: Could not find weights at {weights_path}.")
        return
        
    print(f"Loading Kaggle trained weights from: {weights_path}")
    model = YOLO(weights_path)
    
    print("\n--- 1. Running Validation (Full Dataset) ---")
    val_results = model.val(data=yaml_path, split="val")

    print("\n--- 2. Running Testing (Full Dataset) ---")
    test_results = model.val(data=yaml_path, split="test")
    
    print("\nEvaluation Complete!")
    print(f"Test MAP50-95 Score: {test_results.box.map:.4f}")

if __name__ == "__main__":
    evaluate_kaggle_model()