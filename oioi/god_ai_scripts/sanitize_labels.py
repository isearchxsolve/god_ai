from pathlib import Path
from tqdm import tqdm
import os

DATASET_DIR = Path("yolo_ui_dataset")

def check_labels():
    print(f"Scanning labels in {DATASET_DIR} for invalid boxes...")
    labels = list(DATASET_DIR.rglob("*.txt"))
    
    bad_files = []
    
    for lbl_path in tqdm(labels):
        try:
            with open(lbl_path, "r") as f:
                lines = f.readlines()
                
            if not lines:
                continue # Empty files are fine (Safe images)

            is_bad = False
            for line in lines:
                parts = list(map(float, line.strip().split()))
                
                # YOLO format: class x_center y_center width height
                # All values must be between 0 and 1
                # Width and Height must be > 0
                if len(parts) != 5: continue
                
                cls, cx, cy, w, h = parts
                
                if w <= 0.001 or h <= 0.001: # Check for microscopic boxes
                    print(f"\n[BAD BOX] Too small: {lbl_path.name} (w={w}, h={h})")
                    is_bad = True
                    break
                
                if cx < 0 or cx > 1 or cy < 0 or cy > 1:
                    print(f"\n[BAD BOX] Out of bounds: {lbl_path.name}")
                    is_bad = True
                    break
                    
            if is_bad:
                bad_files.append(lbl_path)

        except Exception as e:
            print(f"Error reading {lbl_path}: {e}")

    if bad_files:
        print(f"\nFound {len(bad_files)} bad label files. Deleting them and their images...")
        for txt_path in bad_files:
            # Delete .txt
            os.remove(txt_path)
            
            # Find and delete .jpg/.png
            # Try both jpg and png
            img_jpg = str(txt_path).replace("labels", "images").replace(".txt", ".jpg")
            img_png = str(txt_path).replace("labels", "images").replace(".txt", ".png")
            
            if os.path.exists(img_jpg): os.remove(img_jpg)
            if os.path.exists(img_png): os.remove(img_png)
            
        print("Cleanup complete.")
    else:
        print("✅ No invalid labels found. The issue might be the Learning Rate.")

if __name__ == "__main__":
    check_labels()