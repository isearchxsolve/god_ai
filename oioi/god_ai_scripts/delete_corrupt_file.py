import os
from pathlib import Path

# The file you found stuck
BAD_FILENAME = "ui_7392.jpg"
DATASET_DIR = Path("yolo_ui_dataset")

def clean_up():
    print(f"Searching for {BAD_FILENAME}...")
    # Find the file recursively
    found_files = list(DATASET_DIR.rglob(BAD_FILENAME))
    
    if not found_files:
        print("File not found! (Maybe you already deleted it?)")
        return

    for p in found_files:
        print(f" -> Found corrupt file at: {p}")
        try:
            # 1. Delete Image
            os.remove(p)
            print("    [DELETED] Image")
            
            # 2. Delete corresponding Label (.txt)
            # Logic: swap 'images'->'labels' and '.jpg'->'.txt'
            txt_path_str = str(p).replace("images", "labels").replace(p.suffix, ".txt")
            txt_path = Path(txt_path_str)
            
            if txt_path.exists():
                os.remove(txt_path)
                print(f"    [DELETED] Label: {txt_path.name}")
            else:
                print("    [INFO] No label file found (might be safe image)")
                
        except Exception as e:
            print(f"    [ERROR] Could not delete: {e}")

if __name__ == "__main__":
    clean_up()