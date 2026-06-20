"""
SAFE SAMPLE INGESTOR
- Copies safe images to the training dataset.
- Generates the REQUIRED empty label files (Negative Samples) for YOLO.
- Helps prevent False Positives during training.
"""

import cv2
import shutil
from pathlib import Path
from tqdm import tqdm

# ================= CONFIGURATION =================
# Path to your folder of SAFE screenshots (Clean Google results, etc.)
SAFE_SOURCE_DIR = Path("search_screenshots/safe")

# Your current dataset destination
DATASET_DIR = Path("google_search_dataset")
DEST_IMAGES = DATASET_DIR / "images" / "train"
DEST_LABELS = DATASET_DIR / "labels" / "train"
# =================================================

def add_negative_samples():
    print("="*60)
    print("ADDING SAFE (NEGATIVE) SAMPLES")
    print("="*60)
    
    # 1. Verify Paths
    if not SAFE_SOURCE_DIR.exists():
        print(f"❌ Error: Source folder '{SAFE_SOURCE_DIR}' does not exist.")
        print("   Please create it and put your clean screenshots inside.")
        return

    DEST_IMAGES.mkdir(parents=True, exist_ok=True)
    DEST_LABELS.mkdir(parents=True, exist_ok=True)

    # 2. Get List of Safe Images
    safe_files = list(SAFE_SOURCE_DIR.glob("*.png")) + list(SAFE_SOURCE_DIR.glob("*.jpg"))
    
    if not safe_files:
        print(f"⚠️  No images found in {SAFE_SOURCE_DIR}")
        return

    print(f"   Found {len(safe_files)} safe images to ingest.")
    
    count = 0
    for img_path in tqdm(safe_files, desc="Ingesting"):
        # A. Copy Image
        dest_img_path = DEST_IMAGES / img_path.name
        
        # Avoid overwriting existing files (in case of name collision)
        if dest_img_path.exists():
            # append _safe to filename
            new_name = f"{img_path.stem}_safe{img_path.suffix}"
            dest_img_path = DEST_IMAGES / new_name
            
        shutil.copy(str(img_path), str(dest_img_path))
        
        # B. Create EMPTY Label File
        # YOLO requires a matching .txt file that is empty for negative samples
        label_name = dest_img_path.stem + ".txt"
        label_path = DEST_LABELS / label_name
        
        with open(label_path, "w") as f:
            pass # Create empty file
            
        count += 1

    print("\n" + "="*60)
    print(f"✅ Successfully added {count} negative samples.")
    print("   Your model will now learn what NOT to detect.")
    print("="*60)
    print("👉 NEXT STEP: Run 'hybrid_trainer_enhanced.py' to split and train.")

if __name__ == "__main__":
    add_negative_samples()