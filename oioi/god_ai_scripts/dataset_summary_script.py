import os
import json
from pathlib import Path

def count_images_in_directory(directory):
    """Count image files in a directory."""
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
    count = 0
    
    if os.path.exists(directory):
        for file in os.listdir(directory):
            if Path(file).suffix.lower() in image_extensions:
                count += 1
    
    return count

def create_dataset_summary(root_dir='final_dataset'):
    """
    Create dataset summary JSON with total images and class weights.
    
    Args:
        root_dir: Root directory containing train/test/val folders
    """
    # Initialize counters
    class_counts = {'safe': 0, 'unsafe': 0}
    
    # Iterate through splits (train, test, val)
    for split in ['train', 'test', 'val']:
        split_path = os.path.join(root_dir, split)
        
        if not os.path.exists(split_path):
            print(f"Warning: {split_path} directory not found, skipping...")
            continue
        
        # Count images in each class
        for class_name in ['safe', 'unsafe']:
            class_path = os.path.join(split_path, class_name)
            count = count_images_in_directory(class_path)
            class_counts[class_name] += count
            print(f"{split}/{class_name}: {count} images")
    
    # Calculate total images
    total_images = sum(class_counts.values())
    
    # Calculate class weights (inverse frequency)
    # Weight = total_samples / (num_classes * class_samples)
    num_classes = len(class_counts)
    class_weights = {}
    
    for class_name, count in class_counts.items():
        if count > 0:
            weight = total_images / (num_classes * count)
            class_weights[class_name] = round(weight, 4)
        else:
            class_weights[class_name] = 0.0
    
    # Create summary dictionary
    summary = {
        "total_images": total_images,
        "class_weights": class_weights
    }
    
    # Write to JSON file
    output_file = os.path.join(root_dir, 'dataset_summary.json')
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*50}")
    print(f"Total images: {total_images}")
    print(f"Safe images: {class_counts['safe']}")
    print(f"Unsafe images: {class_counts['unsafe']}")
    print(f"\nClass weights:")
    print(f"  safe: {class_weights['safe']}")
    print(f"  unsafe: {class_weights['unsafe']}")
    print(f"\nSummary saved to: {output_file}")
    print(f"{'='*50}")
    
    return summary

if __name__ == "__main__":
    # You can change the root directory if needed
    root_directory = 'final_dataset'  # Current directory
    
    print("Analyzing dataset structure...\n")
    create_dataset_summary(root_directory)
