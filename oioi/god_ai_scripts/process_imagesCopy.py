# process_images_fast.py
import shutil
from pathlib import Path
from PIL import Image
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm

CUSTOM_ROOT = Path('custom_sources')
OUTPUT_DIR = Path('final_dataset')
TARGET_SIZE = (224, 224)
NUM_WORKERS = 12  # Change to your CPU cores (8–16 recommended)

def process_image(args):
    src_path, label, split = args
    try:
        with Image.open(src_path) as img:
            img = img.convert('RGB')
            if min(img.size) < 32:
                return None
            img = img.resize(TARGET_SIZE, Image.LANCZOS)

        # This creates: final_dataset/train/safe, final_dataset/val/unsafe, etc.
        dest_folder = OUTPUT_DIR / split / label
        dest_folder.mkdir(parents=True, exist_ok=True)
        dest_path = dest_folder / f"{src_path.stem}.jpg"

        img.save(dest_path, 'JPEG', quality=92, optimize=True, progressive=True)
        return True
    except Exception:
        return False

def main():
    print("Scanning all .jpg files in custom_sources...")
    items = []
    for file_path in CUSTOM_ROOT.rglob("*.jpg"):
        label = "safe" if "safe" in file_path.parts else "unsafe"
        items.append((file_path, label))

    if not items:
        print("No images found! Check your CUSTOM_ROOT path.")
        return

    random.shuffle(items)
    total = len(items)
    train_end = int(total * 0.70)
    val_end = int(total * 0.85)

    tasks = []
    for i, (path, label) in enumerate(items):
        if i < train_end:
            split = "train"
        elif i < val_end:
            split = "val"
        else:
            split = "test"
        tasks.append((path, label, split))

    # Optional: delete old dataset
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
        print("Cleared old final_dataset/")

    # Create full structure in advance (optional, but nice)
    for split in ["train", "val", "test"]:
        for label in ["safe", "unsafe"]:
            (OUTPUT_DIR / split / label).mkdir(parents=True, exist_ok=True)

    print(f"Starting processing of {total:,} images → train/val/test (70/15/15)")
    print(f"Using {NUM_WORKERS} CPU workers...\n")

    success_count = 0
    with ProcessPoolExecutor(max_workers=NUM_WORKERS) as executor:
        futures = [executor.submit(process_image, task) for task in tasks]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Progress", unit="img"):
            if future.result():
                success_count += 1

    print(f"\nALL DONE!")
    print(f"Successfully processed: {success_count:,} images")
    print(f"Dataset ready at: {OUTPUT_DIR.resolve()}")
    print("""
    Folder structure created:
    final_dataset/
    ├── train/
    │   ├── safe/
    │   └── unsafe/
    ├── val/
    │   ├── safe/
    │   └── unsafe/
    └── test/
        ├── safe/
        └── unsafe/
    """)

if __name__ == '__main__':
    main()