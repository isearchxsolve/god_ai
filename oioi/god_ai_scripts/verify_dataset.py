from pathlib import Path
from PIL import Image
from tqdm import tqdm
import os

# Path to your dataset
DATASET_DIR = Path("yolo_ui_dataset")

def verify_images():
    print(f"Scanning {DATASET_DIR} for corrupt images...")
    
    # Find all images (recursive)
    images = list(DATASET_DIR.rglob("*.jpg")) + list(DATASET_DIR.rglob("*.png"))
    print(f"Found {len(images)} images. Checking integrity...")
    
    bad_files = []
    
    for img_path in tqdm(images):
        try:
            # 1. Try to open with PIL (Checks headers)
            with Image.open(img_path) as img:
                img.verify() # Verify file integrity
            
            # 2. Try to reload and check dimensions (Double check)
            with Image.open(img_path) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT) # Force a pixel operation
                
        except Exception as e:
            print(f"\n[CORRUPT] Found bad file: {img_path}")
            print(f"   Error: {e}")
            bad_files.append(img_path)

    if bad_files:
        print(f"\nFound {len(bad_files)} corrupt files. Deleting them...")
        for p in bad_files:
            try:
                os.remove(p)
                # Also try to remove the corresponding label file if it exists
                label_path = str(p).replace("images", "labels").replace(".jpg", ".txt").replace(".png", ".txt")
                if os.path.exists(label_path):
                    os.remove(label_path)
                print(f"   Deleted: {p.name}")
            except:
                print(f"   Could not delete: {p.name}")
    else:
        print("\n✅ All images are healthy!")

if __name__ == "__main__":
    verify_images()