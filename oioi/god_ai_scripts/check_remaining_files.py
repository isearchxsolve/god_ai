from pathlib import Path
from PIL import Image
import sys

if sys.stdout.encoding != 'utf-8':
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

DATASET_DIR = Path("yolo_ui_dataset")

def check_rest():
    print(f"Listing images...")
    images = list(DATASET_DIR.rglob("*.jpg")) + list(DATASET_DIR.rglob("*.png"))
    
    # === START AFTER THE BAD FILE ===
    # You got stuck at 7104. Let's start safely at 7105.
    START_INDEX = 7105
    
    print(f"Total images: {len(images)}")
    
    if len(images) < START_INDEX:
        print("Index out of bounds. You might have deleted enough files that the list is shorter.")
        print("Starting from 0 just to be safe (fast check mode)...")
        subset = images
        current_idx = 0
    else:
        print(f"Skipping first {START_INDEX} images. Checking the rest...")
        subset = images[START_INDEX:]
        current_idx = START_INDEX

    for img_path in subset:
        # Print BEFORE opening. If it hangs, this is the bad filename.
        print(f"[{current_idx}] Checking: {img_path.name} ... ", end="", flush=True)
        
        try:
            with Image.open(img_path) as img:
                img.transpose(Image.FLIP_LEFT_RIGHT) # Force pixel read
            print("OK")
        except KeyboardInterrupt:
            print("\nAborted by user.")
            break
        except Exception as e:
            print(f"\n[CRASH] Found bad file! -> {img_path.name}")
            print("Please delete this file and run script again.")
            break
            
        current_idx += 1

    print("\nCheck complete!")

if __name__ == "__main__":
    check_rest()