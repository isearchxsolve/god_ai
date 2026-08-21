import cv2
import random
import os
from pathlib import Path

# ================= CONFIG =================
DATASET_DIR = Path("google_search_dataset_v2")
IMAGES_DIR = DATASET_DIR / "images" / "train"
LABELS_DIR = DATASET_DIR / "labels" / "train"
OUTPUT_DIR = Path("verification_output")
SAMPLE_SIZE = 50  # How many images to check
# ==========================================

def draw_yolo_boxes(img_path, label_path):
    # Load image
    img = cv2.imread(str(img_path))
    if img is None: return
    h, w = img.shape[:2]

    # Load labels
    if not label_path.exists():
        # This is a SAFE image (no label file or empty file)
        # We draw a green border to indicate "Safe/Empty"
        cv2.rectangle(img, (0,0), (w-1, h-1), (0, 255, 0), 10)
        return img

    with open(label_path, 'r') as f:
        lines = f.readlines()

    # If file exists but is empty, it's also Safe
    if not lines:
        cv2.rectangle(img, (0,0), (w-1, h-1), (0, 255, 0), 10)
        return img

    # Draw Unsafe Boxes (Red)
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 5: continue
        
        # YOLO format: class x_center y_center width height
        cls, cx, cy, bw, bh = map(float, parts)
        
        # Convert to pixels
        x1 = int((cx - bw/2) * w)
        y1 = int((cy - bh/2) * h)
        x2 = int((cx + bw/2) * w)
        y2 = int((cy + bh/2) * h)
        
        # Draw Rectangle (Red for Toxic)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(img, "TOXIC", (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)

    return img

def main():
    if not IMAGES_DIR.exists():
        print(f"❌ Error: Could not find dataset at {IMAGES_DIR}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get list of all images
    all_images = list(IMAGES_DIR.glob("*.png")) + list(IMAGES_DIR.glob("*.jpg"))
    
    if not all_images:
        print("❌ No images found in dataset.")
        return

    # Pick random samples
    samples = random.sample(all_images, min(SAMPLE_SIZE, len(all_images)))
    
    print(f"Generating {len(samples)} verification images in '{OUTPUT_DIR}'...")
    
    for img_path in samples:
        label_path = LABELS_DIR / (img_path.stem + ".txt")
        viz_img = draw_yolo_boxes(img_path, label_path)
        
        if viz_img is not None:
            cv2.imwrite(str(OUTPUT_DIR / f"verify_{img_path.name}"), viz_img)
            
    print("✅ Done! Go open the 'verification_output' folder to check accuracy.")

if __name__ == "__main__":
    main()