from ultralytics import YOLO
import sys
import os

def evaluate_models(yaml_path="data/yolo_full_dataset/full_dataset.yaml"):
    # The actual path to the best weights output by Ultralytics during your training session
    # Adjust "initial_yolo_model2" to "initial_yolo_model" if needed based on what was printed.
    weights_path = os.path.join('runs', 'detect', 'models', 'runs', 'initial_yolo_model2', 'weights', 'best.pt')
    
    if not os.path.exists(weights_path):
        weights_path = os.path.join('runs', 'detect', 'models', 'runs', 'initial_yolo_model', 'weights', 'best.pt')

    print(f"Loading trained weights from: {weights_path}")
    model = YOLO(weights_path)
    
    print("\n--- 1. Running Validation ---")
    # This tests the model on the Validation Split to check general accuracy
    val_results = model.val(data=yaml_path, split="val")
    print("\nValidation Complete. Metrics outputted above.")

    print("\n--- 2. Running Testing ---")
    # This runs the model on the completely unseen Test Split to simulate real-world usage
    # We use .val() with split="test" to get raw metrics, 
    # and .predict() if we wanted visual images saved to the runs folder.
    test_results = model.val(data=yaml_path, split="test")
    print(f"Test MAP50-95 Score: {test_results.box.map}") # Mean Average Precision across 50-95% overlapping

if __name__ == "__main__":
    if len(sys.argv) > 1:
        evaluate_models(sys.argv[1])
    else:
        evaluate_models()