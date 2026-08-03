from ultralytics import YOLO
import os

def evaluate_subset():
    weights_path = os.path.join('runs', 'detect', 'subset_10pct_100ep', 'weights', 'best.pt')
    yaml_path = os.path.join('data', 'yolo_subset_dataset', 'subset_dataset.yaml')
    
    if not os.path.exists(weights_path):
        print(f"Error: Could not find weights at {weights_path}. Make sure the training finished successfully.")
        return
        
    print(f"Loading trained weights from: {weights_path}")
    model = YOLO(weights_path)
    
    print("\n--- 1. Running Validation (Subset) ---")
    val_results = model.val(data=yaml_path, split="val")

    print("\n--- 2. Running Testing (Subset) ---")
    test_results = model.val(data=yaml_path, split="test")
    
    print("\nEvaluation Complete!")
    print(f"Test MAP50-95 Score: {test_results.box.map:.4f}")

if __name__ == "__main__":
    evaluate_subset()