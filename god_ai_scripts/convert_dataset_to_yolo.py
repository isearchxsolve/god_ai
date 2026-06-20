import os
import shutil
import cv2
from pathlib import Path
from tqdm import tqdm
import sys

# === CONFIGURATION ===
# Path to your current dataset (the one with 'train/safe', 'train/unsafe')
SOURCE_DATASET = Path("final_dataset") 
# Where to create the new YOLO format dataset
YOLO_DATASET = Path("yolo_dataset")
# List of toxic words to auto-detect (add your own)

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

def setup_directories():
    if YOLO_DATASET.exists():
        shutil.rmtree(YOLO_DATASET)
    
    # Create YOLO structure: images/train, labels/train, etc.
    for split in ["train", "val"]:
        (YOLO_DATASET / "images" / split).mkdir(parents=True, exist_ok=True)
        (YOLO_DATASET / "labels" / split).mkdir(parents=True, exist_ok=True)

def normalize_bbox(x, y, w, h, img_w, img_h):
    # YOLO format: class_id center_x center_y width height (normalized 0-1)
    # class_id is always 0 for "toxic_region"
    center_x = (x + w / 2) / img_w
    center_y = (y + h / 2) / img_h
    norm_w = w / img_w
    norm_h = h / img_h
    return f"0 {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}"

def auto_label_image(img_path, label_path):
    """
    Analyzes an unsafe image to generate YOLO labels.
    Strategy:
    1. OCR: If toxic text found, label ONLY the text region.
    2. Fallback: If no text, label the center 90% of the image (Visual Toxicity).
    """
    # Read image
    img = cv2.imread(str(img_path))
    if img is None: 
        return
    lines = []
    
    # --- STRATEGY 1: OCR (Text Detection) ---
    fallback_box = "0 0.5 0.5 0.9 0.9"
    lines.append(fallback_box)

    # Write the label file
    if lines:
        with open(label_path, "w") as f:
            f.write("\n".join(lines))

def process_dataset():
    print(f"Converting dataset from: {SOURCE_DATASET} -> {YOLO_DATASET}")
    setup_directories()
    
    # Process both splits
    for split in ["train", "val"]:
        print(f"\nProcessing {split} set...")
        
        # 1. Process SAFE images (Empty Label Files)
        safe_path = SOURCE_DATASET / split / "safe"
        if safe_path.exists():
            for img_file in tqdm(list(safe_path.glob("*.*")), desc="Safe Images"):
                if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp']: continue
                
                # Copy image
                shutil.copy(img_file, YOLO_DATASET / "images" / split / img_file.name)
                
                # Create EMPTY label file (Safety Signal)
                label_file = YOLO_DATASET / "labels" / split / (img_file.stem + ".txt")
                with open(label_file, "w") as f:
                    pass # Empty file = "No objects here"

        # 2. Process UNSAFE images (Auto-Labeling)
        unsafe_path = SOURCE_DATASET / split / "unsafe"
        if unsafe_path.exists():
            for img_file in tqdm(list(unsafe_path.glob("*.*")), desc="Unsafe Images"):
                if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.bmp']: continue

                # Copy image
                dest_img = YOLO_DATASET / "images" / split / img_file.name
                shutil.copy(img_file, dest_img)
                
                # Generate Label
                dest_label = YOLO_DATASET / "labels" / split / (img_file.stem + ".txt")
                auto_label_image(img_file, dest_label)

    # Create dataset.yaml for YOLO training
    yaml_content = f"""
path: {YOLO_DATASET.absolute().as_posix()}
train: images/train
val: images/val

names:
  0: toxic_region
"""
    with open("toxic_data.yaml", "w") as f:
        f.write(yaml_content)
    
    print("\n" + "="*50)
    print("CONVERSION COMPLETE!")
    print("="*50)
    print(f"1. Dataset ready at: {YOLO_DATASET}")
    print(f"2. Config file ready: toxic_data.yaml")
    print("3. Next step: Run 'train_yolo.py'")

if __name__ == "__main__":
    process_dataset()