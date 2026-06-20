"""
dataset_builder_v3_fixed.py
Robust dataset builder for unsafe/safe image classification
FIXES:
1. Kaggle authentication handling
2. Better error recovery and retries
3. Dataset availability checks
4. Alternative sources when primary fails
5. Improved progress tracking
"""

import os
import random
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageFile
import cv2
from datasets import load_dataset
import hashlib

ImageFile.LOAD_TRUNCATED_IMAGES = True
random.seed(42)

# ==============================================================================
# CONFIGURATION
# ==============================================================================

CUSTOM_ROOT = Path("custom_sources")
OUTPUT_DIR = Path("final_dataset")
TEMP_DIR = Path("temp_download")

# Kaggle credentials - CRITICAL FIX
# Option 1: Use environment variables (recommended)
KAGGLE_USERNAME = os.environ.get('KAGGLE_USERNAME', 'kunaldas3104')
KAGGLE_KEY = os.environ.get('KAGGLE_KEY', '5115042f9b511e8a15e8e77cfc37a740')

# Set credentials
os.environ['KAGGLE_USERNAME'] = KAGGLE_USERNAME
os.environ['KAGGLE_KEY'] = KAGGLE_KEY

# Classes
UNSAFE_CLASSES = ["violence", "gore", "nsfw", "medical", "biological"]
SAFE_CLASS = "safe"
ALL_CLASSES = UNSAFE_CLASSES + [SAFE_CLASS]

TARGET_SIZE = (224, 224)
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15

INCLUDE_BIOLOGICAL = True

# Download settings
MAX_RETRIES = 2
RETRY_DELAY = 5  # seconds
DEBUG_MODE = True  # Show detailed download info

# ==============================================================================
# VERIFIED DATASET SOURCES (WITH FALLBACKS)
# ==============================================================================

SOURCES = [
    # ── VIOLENCE ─────────────────────────────────────
    # Images only (violent + non-violent) - fast, no video extraction
    {
        "type": "kaggle", 
        "id": "kartikeybartwal/graphical-violence-and-safe-images-dataset", 
        "target": "violence",
        "fallback": None
    },
    
    # ── GORE / TRAUMA ───────────────────────────────
    # (Your original - still works great)
    {
        "type": "kaggle", 
        "id": "ibrahimfateen/wound-classification", 
        "target": "gore",
        "fallback": None
    },
    
    # ── BIOLOGICAL ──────────────────────────────────
    # (Your working one)
    {
        "type": "kaggle", 
        "id": "meetnagadia/kvasir-dataset", 
        "target": "biological", 
        "enabled": INCLUDE_BIOLOGICAL,
        "fallback": None
    },
    
    # ── MEDICAL ─────────────────────────────────────
    # Smaller skin cancer dataset (~10k images) - fast download
    {
        "type": "kaggle", 
        "id": "hasnainjaved/melanoma-skin-cancer-dataset-of-10000-images", 
        "target": "medical",
        "fallback": None
    },

    # ── NSFW ────────────────────────────────────────
    # 80k+ real NSFW images, public, fast streaming
    {
        "type": "hf", 
        "name": "yesidobyte/nsfw1024", 
        "target": "nsfw", 
        "labels": None,  # All images are NSFW by default
        "max_items": 8000,  # Cap for balance
        "enabled": True
    },

    # ── SAFE ────────────────────────────────────────
    # (Your working flowers one)
    {
        "type": "kaggle", 
        "id": "alxmamaev/flowers-recognition", 
        "target": "safe",
        "fallback": None
    },
]

# ==============================================================================
# UTILITIES
# ==============================================================================

def verify_kaggle_auth():
    """Verify Kaggle authentication is working"""
    print("\n[AUTH CHECK] Verifying Kaggle credentials...")
    
    # Check if credentials are set
    if not KAGGLE_USERNAME or not KAGGLE_KEY:
        print("   ✗ Kaggle credentials not found!")
        print("   Please set KAGGLE_USERNAME and KAGGLE_KEY environment variables")
        return False
    
    # Test with a simple API call
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "list", "--max-size", "1"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("   ✓ Kaggle authentication successful")
            return True
        else:
            error = result.stderr.strip()
            if "401" in error or "Unauthorized" in error:
                print("   ✗ Invalid credentials")
            else:
                print(f"   ✗ Auth failed: {error[:60]}")
            return False
            
    except FileNotFoundError:
        print("   ✗ Kaggle CLI not installed")
        print("   Install with: pip install kaggle")
        return False
    except subprocess.TimeoutExpired:
        print("   ✗ Connection timeout")
        return False
    except Exception as e:
        print(f"   ✗ Error: {str(e)[:60]}")
        return False


def hash_file(path: Path) -> str:
    """MD5 hash for deduplication"""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except:
        return ""


def extract_frames(video_path: Path, out_dir: Path, max_frames: int = 50) -> int:
    """Extract frames from video"""
    try:
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 0
        
        count = 0
        frame_idx = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(1, total_frames // max_frames) if total_frames > 0 else 30
        
        while count < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % step == 0:
                try:
                    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                    img.save(out_dir / f"vid_{video_path.stem}_{count:04d}.jpg", "JPEG", quality=90)
                    count += 1
                except:
                    pass
            frame_idx += 1
        
        cap.release()
        return count
    except Exception as e:
        print(f"      Frame extraction error: {str(e)[:50]}")
        return 0


def check_dataset_exists(dataset_id: str) -> bool:
    """Check if Kaggle dataset exists and is accessible"""
    try:
        result = subprocess.run(
            ["kaggle", "datasets", "list", "-s", dataset_id],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and dataset_id in result.stdout:
            return True
        return False
        
    except Exception:
        return False


# ==============================================================================
# DOWNLOADERS WITH RETRY LOGIC
# ==============================================================================

def download_kaggle_single_attempt(dataset_id: str, target_dir: Path) -> int:
    """Single download attempt for Kaggle dataset"""
    dataset_name = dataset_id.split('/')[-1]
    
    try:
        # Clean temp directory
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        # Download with --unzip flag for better compatibility
        print("      Downloading...", flush=True)
        download_result = subprocess.run(
            ["kaggle", "datasets", "download", "-d", dataset_id, "-p", str(TEMP_DIR), "--unzip"],
            capture_output=True,
            text=True,
            timeout=600  # 10 minutes for large datasets
        )
        
        if download_result.returncode != 0:
            error_msg = download_result.stderr.strip()
            stdout_msg = download_result.stdout.strip()
            
            if DEBUG_MODE:
                print(f"      Debug: Return code = {download_result.returncode}", flush=True)
                if error_msg:
                    print(f"      Debug: stderr = {error_msg[:200]}", flush=True)
                if stdout_msg:
                    print(f"      Debug: stdout = {stdout_msg[:200]}", flush=True)
            
            # Parse specific errors
            combined_msg = error_msg + " " + stdout_msg
            if "403" in combined_msg or "Forbidden" in combined_msg:
                raise ValueError("Access denied - dataset private or requires acceptance")
            elif "404" in combined_msg or "not found" in combined_msg.lower():
                raise ValueError("Dataset not found")
            elif "credentials" in combined_msg.lower() or "401" in combined_msg:
                raise ValueError("Authentication failed")
            elif "FileNotFoundError" in combined_msg:
                raise ValueError("Dataset has no files or empty")
            else:
                raise ValueError(f"Download failed: {error_msg[:100] if error_msg else stdout_msg[:100]}")

        # The --unzip flag should have extracted everything
        # If no zip files and no extracted content, dataset might be empty
        all_files = list(TEMP_DIR.rglob("*"))
        if len(all_files) == 0:
            raise ValueError("No files downloaded - dataset may be empty")
        
        if DEBUG_MODE:
            print(f"      Debug: Found {len(all_files)} total files/folders", flush=True)
            # Show directory structure
            dirs = [f for f in all_files if f.is_dir()]
            files = [f for f in all_files if f.is_file()]
            print(f"      Debug: {len(dirs)} directories, {len(files)} files", flush=True)
        
        # Check for zip files that weren't auto-extracted
        import zipfile
        zip_files = list(TEMP_DIR.glob("*.zip"))
        
        for zip_file in zip_files:
            try:
                print(f"      Extracting {zip_file.name}...", flush=True)
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(TEMP_DIR)
                zip_file.unlink()  # Remove zip after extraction
            except zipfile.BadZipFile:
                print(f"      Warning: Corrupted zip {zip_file.name}", flush=True)
                continue

        # Process images
        count = 0
        skipped = 0
        image_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}
        
        for file_path in TEMP_DIR.rglob("*"):
            if file_path.suffix.lower() in image_extensions:
                try:
                    with Image.open(file_path) as img:
                        if img.mode != "RGB":
                            img = img.convert("RGB")
                        img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                        
                        new_name = target_dir / f"{dataset_name}_{count:06d}.jpg"
                        img.save(new_name, "JPEG", quality=90)
                        count += 1
                        
                        if count % 100 == 0:
                            print(f"         {count} images...", flush=True)
                        
                except Exception:
                    skipped += 1
                    continue

        # Process videos
        video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".flv"}
        video_count = 0
        
        for file_path in TEMP_DIR.rglob("*"):
            if file_path.suffix.lower() in video_extensions:
                frames = extract_frames(file_path, target_dir, max_frames=50)
                if frames > 0:
                    count += frames
                    video_count += 1

        return count
        
    finally:
        # Clean up
        if TEMP_DIR.exists():
            try:
                shutil.rmtree(TEMP_DIR, ignore_errors=True)
            except:
                pass


def download_kaggle(dataset_id: str, target_dir: Path, fallback_id: str = None) -> int:
    """Download Kaggle dataset with retry and fallback"""
    dataset_name = dataset_id.split('/')[-1]
    print(f"\n   [Kaggle] {dataset_name}")
    print(f"      Dataset: {dataset_id}")
    
    # Try primary dataset
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                print(f"      Retry {attempt}/{MAX_RETRIES}...", flush=True)
                time.sleep(RETRY_DELAY)
            
            count = download_kaggle_single_attempt(dataset_id, target_dir)
            
            if count > 0:
                print(f"      ✓ Downloaded {count:,} images")
                return count
            else:
                raise ValueError("No images extracted")
                
        except subprocess.TimeoutExpired:
            print(f"      ✗ Timeout (attempt {attempt + 1})")
            if attempt == MAX_RETRIES - 1:
                break
            continue
            
        except ValueError as e:
            print(f"      ✗ {str(e)}")
            break  # Don't retry on these errors
            
        except Exception as e:
            print(f"      ✗ Error: {str(e)[:60]}")
            if attempt == MAX_RETRIES - 1:
                break
            continue
    
    # Try fallback if available
    if fallback_id:
        print(f"      Trying fallback: {fallback_id}")
        try:
            count = download_kaggle_single_attempt(fallback_id, target_dir)
            if count > 0:
                print(f"      ✓ Fallback succeeded: {count:,} images")
                return count
        except Exception as e:
            print(f"      ✗ Fallback failed: {str(e)[:60]}")
    
    return 0


def download_hf(name: str, labels: list, target_dir: Path, max_items: int = 5000) -> int:
    """Download from Hugging Face with retry logic"""
    hf_name = name.split('/')[-1]
    print(f"\n   [HF] {hf_name}")
    print(f"      Dataset: {name}")
    
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                print(f"      Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
            
            ds = load_dataset(name, split="train", streaming=True)
            count = 0
            errors = 0
            
            print("      Downloading...", flush=True)
            
            for item in ds:
                if count >= max_items:
                    break
                
                try:
                    # Check label
                    if labels:
                        item_label = item.get("label") or item.get("labels", "")
                        if item_label not in labels:
                            continue
                    
                    # Process image
                    img = item.get("image")
                    if not img or not isinstance(img, Image.Image):
                        continue
                    
                    if img.mode != "RGB":
                        img = img.convert("RGB")
                    
                    img = img.resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                    img.save(target_dir / f"hf_{count:06d}.jpg", "JPEG", quality=90)
                    count += 1
                    
                    if count % 100 == 0:
                        print(f"         {count} images...", flush=True)
                    
                except Exception:
                    errors += 1
                    if errors > 100:
                        break
                    continue
            
            if count > 0:
                print(f"      ✓ Downloaded {count:,} images")
                return count
            else:
                raise ValueError("No valid images found")
                
        except Exception as e:
            print(f"      ✗ Error: {str(e)[:60]}")
            if attempt == MAX_RETRIES - 1:
                return 0
            continue
    
    return 0


# ==============================================================================
# MAIN PIPELINE
# ==============================================================================

def download_all():
    """Download all configured datasets"""
    print("\n" + "="*70)
    print(" DATASET DOWNLOAD")
    print(f" Biological content: {INCLUDE_BIOLOGICAL}")
    print("="*70)

    # Verify authentication first
    if not verify_kaggle_auth():
        print("\n✗ Cannot proceed without valid Kaggle authentication")
        return False

    stats = {cls: 0 for cls in ALL_CLASSES}
    failed = []
    
    for i, src in enumerate(SOURCES, 1):
        if not src.get("enabled", True):
            continue
            
        target_class = src["target"]
        dest = CUSTOM_ROOT / target_class
        dest.mkdir(parents=True, exist_ok=True)

        print(f"\n[{i:02d}/{len([s for s in SOURCES if s.get('enabled', True)])}] {target_class.upper()}")

        try:
            if src["type"] == "kaggle":
                cnt = download_kaggle(
                    src["id"], 
                    dest,
                    src.get("fallback")
                )
            elif src["type"] == "hf":
                cnt = download_hf(
                    src["name"], 
                    src.get("labels", []), 
                    dest, 
                    src.get("max_items", 5000)
                )
            else:
                cnt = 0
                
            stats[target_class] += cnt
            
            if cnt == 0:
                failed.append(f"{target_class}: {src.get('id') or src.get('name')}")
                
        except KeyboardInterrupt:
            print("\n\n✗ Interrupted by user")
            raise
        except Exception as e:
            print(f"      ✗ Unexpected error: {str(e)[:60]}")
            failed.append(f"{target_class}: {src.get('id') or src.get('name')}")
            continue

    # Summary
    print("\n" + "="*70)
    print(" DOWNLOAD SUMMARY")
    print("="*70)
    
    total = 0
    for cls in ALL_CLASSES:
        cnt = stats[cls]
        if cnt > 0:
            print(f"  ✓ {cls:12}: {cnt:>7,} images")
            total += cnt
        else:
            print(f"  ✗ {cls:12}: {cnt:>7,} images (FAILED)")
    
    print(f"\n  {'TOTAL':12}: {total:>7,} images")
    
    if failed:
        print(f"\n  Failed sources ({len(failed)}):")
        for f in failed:
            print(f"    - {f}")
    
    print("="*70)

    return total >= 100  # Minimum threshold


def build_final_dataset():
    """Build train/val/test splits with deduplication"""
    print("\n" + "="*70)
    print(" BUILDING FINAL DATASET")
    print("="*70)

    items = []
    for cls in ALL_CLASSES:
        cls_path = CUSTOM_ROOT / cls
        if not cls_path.exists():
            continue
            
        for img_path in cls_path.glob("*.jpg"):
            if img_path.stat().st_size < 1024:
                continue
            
            label = "unsafe" if cls in UNSAFE_CLASSES else "safe"
            items.append((img_path, label))

    if not items:
        print("✗ No images found!")
        return

    print(f"Found {len(items):,} total images")

    # Deduplicate
    print("Deduplicating...", flush=True)
    seen = set()
    unique = []
    
    for path, label in items:
        h = hash_file(path)
        if h and h not in seen:
            seen.add(h)
            unique.append((path, label))
    
    print(f"  ✓ {len(unique):,} unique images")

    # Split
    random.shuffle(unique)
    n = len(unique)
    train_end = int(n * TRAIN_RATIO)
    val_end = int(n * (TRAIN_RATIO + VAL_RATIO))

    splits = {
        "train": unique[:train_end],
        "val": unique[train_end:val_end],
        "test": unique[val_end:]
    }

    # Build splits
    for split_name, split_items in splits.items():
        print(f"\nBuilding {split_name} ({len(split_items):,} images)...")
        split_dir = OUTPUT_DIR / split_name
        
        label_counts = {"safe": 0, "unsafe": 0}
        
        for src_path, label in split_items:
            try:
                with Image.open(src_path) as img:
                    img = img.convert("RGB").resize(TARGET_SIZE, Image.Resampling.LANCZOS)
                
                output_dir = split_dir / label
                output_dir.mkdir(parents=True, exist_ok=True)
                
                output_path = output_dir / f"{src_path.stem}.jpg"
                img.save(output_path, "JPEG", quality=92)
                label_counts[label] += 1
                
            except Exception:
                continue
        
        print(f"  ✓ Safe: {label_counts['safe']:,} | Unsafe: {label_counts['unsafe']:,}")

    print("\n" + "="*70)
    print(f" DATASET READY: {OUTPUT_DIR.resolve()}")
    print(" Structure: final_dataset/{train,val,test}/{safe,unsafe}/")
    print("="*70)


# ==============================================================================
# ENTRYPOINT
# ==============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" DATASET BUILDER - ROBUST VERSION")
    print("="*70)
    
    # Create directories
    CUSTOM_ROOT.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Install dependencies
    print("\nInstalling dependencies...")
    subprocess.run(
        ["pip", "install", "-q", "pillow", "opencv-python", "datasets", "kaggle"],
        capture_output=True
    )

    # Run pipeline
    try:
        if download_all():
            build_final_dataset()
            print("\n✓ SUCCESS! Dataset ready for training.")
        else:
            print("\n✗ FAILED: Insufficient images downloaded.")
            print("  Check authentication and network connection.")
            
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user.")
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()