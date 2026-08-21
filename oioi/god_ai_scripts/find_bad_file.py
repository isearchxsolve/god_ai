from pathlib import Path
from PIL import Image
import os
import sys

# Windows Console Fix
if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATASET_DIR = Path("yolo_ui_dataset")

def find_the_bad_one():
    print(f"Listing images in {DATASET_DIR}...")
    
    # 1. Get exact same list as before
    images = list(DATASET_DIR.rglob("*.jpg")) + list(DATASET_DIR.rglob("*.png"))
    
    print(f"Total images: {len(images)}")
    
    # 2. Skip the first 7000 (since we know they are safe)
    start_index = 7000
    subset = images[start_index:]
    
    print(f"Skipping first {start_index} images. Starting check from index {start_index}...")

    for i, img_path in enumerate(subset):
        current_idx = start_index + i
        
        # PRINT BEFORE PROCESSING (This identifies the killer)
        print(f"[{current_idx}] Checking: {img_path.name} ... ", end="", flush=True)
        
        try:
            # Full deep check (Force pixel load)
            with Image.open(img_path) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT)
            print("OK")
            
        except Exception as e:
            print(f"\n[CRASH] Found bad file! -> {img_path.name}")
            print(f"Error: {e}")
            delete_file(img_path)
        except KeyboardInterrupt:
            print("\nScript stopped by user.")
            break

def delete_file(img_path):
    try:
        os.remove(img_path)
        # Try to delete associated label too
        txt_path = str(img_path).replace("images", "labels").replace(".jpg", ".txt").replace(".png", ".txt")
        if os.path.exists(txt_path):
            os.remove(txt_path)
        print(f" -> DELETED CORRUPT FILES: {img_path.name}")
    except:
        print(f" -> Could not delete {img_path.name}. Please delete manually.")

if __name__ == "__main__":
    find_the_bad_one()