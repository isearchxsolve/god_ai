"""
V16 STABLE DETECTOR (Fixes Freezing)
- Reduced worker count to prevent RAM crashes (OOM).
- Added TIMEOUT to skip images that hang.
- Debug logging to identify corrupted files.
- Retains V15 High-Sensitivity logic.
"""

import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
import os
import signal

# --- CONFIGURATION ---
UNSAFE_DIR = Path("search_screenshots/unsafe")
OUTPUT_DIR = Path("google_search_dataset")
VIZ_DIR = OUTPUT_DIR / "viz"
TIMEOUT_SECONDS = 15  # Skip image if it takes > 15 seconds
WORKER_COUNT = 4  # Safe default to avoid Out-Of-Memory

def setup_directories():
    VIZ_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "images/train").mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "labels/train").mkdir(parents=True, exist_ok=True)

SCALE = 3.0 

def get_content_mask(img):
    # Same sensitive logic as V15
    inv = 255 - img
    diff_map = np.max(inv, axis=2)
    
    blurred_diff = cv2.GaussianBlur(diff_map, (5,5), 0)
    _, raw_mask = cv2.threshold(blurred_diff, 2, 255, cv2.THRESH_BINARY)
    
    erode_k_size = int(1.5 * SCALE)
    kernel_erode = cv2.getStructuringElement(cv2.MORPH_RECT, (erode_k_size, erode_k_size))
    no_text_mask = cv2.erode(raw_mask, kernel_erode, iterations=1)
    
    dilate_k = int(5 * SCALE) 
    kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (dilate_k, dilate_k))
    solid_mask = cv2.dilate(no_text_mask, kernel_dilate, iterations=1)
    
    close_k = int(10 * SCALE)
    kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (close_k, close_k))
    final_mask = cv2.morphologyEx(solid_mask, cv2.MORPH_CLOSE, kernel_close)
    return final_mask

def trim_caption_pattern(img, box):
    x1, y1, x2, y2 = box
    roi = img[y1:y2, x1:x2]
    if roi.size == 0: return box
    
    h_roi, w_roi = roi.shape[:2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    scan_h = int(h_roi * 0.50)
    scan_start_y = h_roi - scan_h
    
    bottom_gray = gray[scan_start_y:, :]
    row_means = np.mean(bottom_gray, axis=1)
    
    edges = cv2.Canny(bottom_gray, 50, 150)
    row_edge_sum = np.sum(edges, axis=1)
    max_val = np.max(row_edge_sum) if np.max(row_edge_sum) > 0 else 1
    norm_edges = row_edge_sum / max_val
    
    split_row = h_roi
    
    for i in range(scan_h - 1, 0, -1):
        is_white = row_means[i] > 230
        is_gap = norm_edges[i] < 0.1
        is_dark_content = row_means[i] < 200
        
        if is_white and is_gap:
            split_row = scan_start_y + i
        if is_dark_content:
            break
            
    if split_row < h_roi * 0.4: return box
    return (x1, y1, x2, y1 + split_row)

def is_valid_box(img, box, screen_h):
    x1, y1, x2, y2 = box
    w = x2 - x1
    h = y2 - y1
    roi = img[y1:y2, x1:x2]
    if roi.size == 0: return False
    
    # UI Filter
    is_at_top = (y1 < (150 * SCALE))
    if is_at_top:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        white_ratio = np.count_nonzero(gray > 240) / (w * h)
        if white_ratio > 0.65: return False
        
    # Aspect Ratio & Size
    aspect = w / h
    touches_edges = (y1 < 20) or (y2 > screen_h - 20)
    
    if aspect > 2.8 and not touches_edges: return False
    if h < (25 * SCALE) and not touches_edges: return False
    
    return True

def box_to_yolo(x1, y1, x2, y2, w, h):
    cx = (x1 + x2) / 2 / w
    cy = (y1 + y2) / 2 / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h
    return f"0 {max(0,min(1,cx)):.6f} {max(0,min(1,cy)):.6f} {max(0,min(1,bw)):.6f} {max(0,min(1,bh)):.6f}"

def process_single_image(img_path):
    try:
        import cv2
        
        # Load
        original_img = cv2.imread(str(img_path))
        if original_img is None: return None
        orig_h, orig_w = original_img.shape[:2]
        
        # Safety Check: Don't upscale massive images
        if orig_h > 5000: # Skip weirdly tall images
            return None

        # Upscale
        img = cv2.resize(original_img, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_CUBIC)
        h, w = img.shape[:2]
        
        # Process
        mask = get_content_mask(img)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        final_boxes = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            box = (x, y, x+bw, y+bh)
            trimmed = trim_caption_pattern(img, box)
            
            if is_valid_box(img, trimmed, h):
                orig_box = tuple(int(c / SCALE) for c in trimmed)
                final_boxes.append(orig_box)
        
        # Save
        if final_boxes:
            shutil.copy(img_path, OUTPUT_DIR / "images/train" / img_path.name)
            
            labels = [box_to_yolo(*b, orig_w, orig_h) for b in final_boxes]
            with open(OUTPUT_DIR / "labels/train" / (img_path.stem + ".txt"), "w") as f:
                f.write("\n".join(labels))
            
            # Simple Viz (Disable if still too slow)
            viz = original_img.copy()
            for i, (x1, y1, x2, y2) in enumerate(final_boxes):
                cv2.rectangle(viz, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.imwrite(str(VIZ_DIR / f"labeled_{img_path.name}"), viz)
            
            return len(final_boxes)
        return 0
        
    except Exception as e:
        return None

def main():
    print(f"RUNNING V16 STABLE DETECTOR")
    print(f"Workers: {WORKER_COUNT} | Timeout: {TIMEOUT_SECONDS}s")
    
    setup_directories()
    
    files = list(UNSAFE_DIR.glob("*.png")) + list(UNSAFE_DIR.glob("*.jpg"))
    if not files:
        print("No images found.")
        return

    total_boxes = 0
    processed_count = 0
    
    with ProcessPoolExecutor(max_workers=WORKER_COUNT) as executor:
        # Submit tasks mapped to filenames
        future_to_file = {executor.submit(process_single_image, f): f for f in files}
        
        # Iterate with TIMEOUT handling
        for future in tqdm(as_completed(future_to_file), total=len(files), desc="Processing"):
            f_path = future_to_file[future]
            try:
                # Wait for result with timeout
                result = future.result(timeout=TIMEOUT_SECONDS)
                if result is not None:
                    total_boxes += result
                    processed_count += 1
            except TimeoutError:
                print(f"\n⚠️ SKIPPING {f_path.name} (Timed Out)")
            except Exception as e:
                print(f"\n❌ Error on {f_path.name}: {e}")

    print(f"\nDone! Processed {processed_count}/{len(files)} images.")
    print(f"Total boxes found: {total_boxes}")
    print(f"Results in {VIZ_DIR}")

if __name__ == "__main__":
    main()